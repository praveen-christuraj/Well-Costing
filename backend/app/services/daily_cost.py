"""Daily cost workflow.

Everything the Daily Costs page needs, minus the HTTP:

* reading a day (header + lines + well configuration) and pricing it with the
  framework-free engine in :mod:`app.domain.daily_costing`;
* building the **AFE rate card** the page's pickers use, so every unit rate the
  user sees comes from the AFE the day is recorded against;
* validating and persisting a whole day atomically (draft → submitted);
* flattening days into export rows for the daily costs report.

Money rules live only in the domain engine; this module resolves *which* rate
applies (AFE rate card, Master Data catalogue, manual entry) and keeps the
scope (section / phase / well sub activity) honest.
"""

from __future__ import annotations

import threading
from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, object_session

from app.domain import daily_costing as engine
from app.domain.afe_costing import (
    BASIS_DAILY,
    BASIS_PER_SECTION,
    BASIS_PER_SERVICE,
    GROUP_CONSUMABLES,
    GROUP_SERVICES,
    GROUP_TANGIBLES,
    UNIT_HOURS,
    effective_rate,
    money,
    normalize_basis,
    normalize_category,
    scope_label,
    to_decimal,
)
from app.models.afe import Afe, AfeConsumableLine
from app.models.catalogue import DrillBit, MudChemical, Service, Tangible
from app.models.daily_cost import (
    DailyCostConsumableLine,
    DailyCostEntry,
    DailyCostServiceLine,
    DailyCostTangibleLine,
)
from app.models.rig_well import Well
from app.models.user import User
from app.models.well_sub_activity import WellSubActivity
from app.schemas.daily_cost import (
    DailyConsumableLineOut,
    DailyCostDayOut,
    DailyCostEntryOut,
    DailyCostSaveIn,
    DailyServiceLineOut,
    DailyTangibleLineOut,
    RateCardServiceOut,
)
from app.services.afe_estimation import build_well_scope, compile_estimate, load_afe
from app.services.well_configuration import build_configuration_out

#: Serializes the read-modify-write of one day (double-clicked saves must not
#: stack two copies of the same lines).
_DAY_SAVE_LOCK = threading.Lock()

FUEL_CODE = "FUEL"
FUEL_NAME = "Fuel"
CEMENT_CODE = "CEM-ADD"
CEMENT_NAME = "Cement Additives"


class DailyCostValidationError(ValueError):
    """Raised for anything the user must fix before a day can be saved."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def entry_code(well_code: str, cost_date: date) -> str:
    """The day's stable reference: ``WELL001/20260830``."""

    return f"{(well_code or 'WELL').strip().upper()}/{cost_date.strftime('%Y%m%d')}"


def afe_code_of(entry: DailyCostEntry) -> str | None:
    """The code of the AFE a day is recorded against.

    Read with a scalar query rather than through the ``entry.afe``
    relationship: loading a whole ``Afe`` pulls its eagerly loaded estimate
    lines (and their cyclic back-references) into the query, which costs
    seconds on the daily list. The day only ever needs the code.
    """

    if entry.afe_id is None:
        return None
    session = object_session(entry)
    if session is None:
        return None
    return session.scalar(select(Afe.afe_code).where(Afe.id == entry.afe_id))


def entry_totals(entry: DailyCostEntry) -> tuple[Decimal, Decimal, Decimal]:
    """Sum the persisted line amounts of one day per cost group."""

    services = money(sum((to_decimal(line.amount) for line in entry.service_lines), Decimal("0")))
    consumables = money(sum((to_decimal(line.amount) for line in entry.consumable_lines), Decimal("0")))
    tangibles = money(sum((to_decimal(line.amount) for line in entry.tangible_lines), Decimal("0")))
    return services, consumables, tangibles


def _display(code: str | None, name: str | None) -> str | None:
    if code and name:
        return f"{code} - {name}"
    return code or name


def _sub_activity_display(line: DailyCostServiceLine | DailyCostConsumableLine) -> str | None:
    sub = getattr(line, "sub_activity", None)
    if sub is None:
        return None
    activity_code = sub.activity.activity_code if sub.activity else None
    label = _display(sub.sub_activity_code, sub.sub_activity_name) or ""
    if activity_code:
        return f"{label} ({activity_code})" if label else activity_code
    return label or None


# ---------------------------------------------------------------------------
# The AFE rate card
# ---------------------------------------------------------------------------


def build_rate_card(db: Session, afe: Afe | None) -> dict[int, engine.RateCardEntry]:
    """What the AFE says about each service — the source of every unit rate.

    A service can sit on more than one AFE line (for example one line per hole
    section). The card merges them: the first line decides the charging basis
    and the per-service price, and the rates / section rates of every line are
    unioned so a daily line can be priced against any of them.
    """

    del db  # the AFE relationship already carries the lines
    card: dict[int, engine.RateCardEntry] = {}
    if afe is None:
        return card
    for line in afe.service_lines:
        rates = {rate.category: to_decimal(rate.unit_rate) for rate in line.rates}
        section_rates = tuple(
            engine.SectionRateEntry(
                section_id=entry.section_id,
                phase_id=entry.phase_id,
                amount=to_decimal(entry.amount),
            )
            for entry in line.section_rates
        )
        existing = card.get(line.service_id)
        if existing is None:
            card[line.service_id] = engine.RateCardEntry(
                service_id=line.service_id,
                service_code=line.service.service_code if line.service else "",
                service_name=line.service.service_name if line.service else "",
                provider_type=line.service.provider_type if line.service else "",
                charging_basis=line.charging_basis,
                afe_line_id=line.id,
                rates=rates,
                per_service_amount=to_decimal(line.per_service_amount),
                section_rates=section_rates,
                section_id=line.section_id,
                phase_id=line.phase_id,
            )
            continue
        merged_rates = dict(existing.rates)
        merged_rates.update(rates)
        seen = {(entry.section_id, entry.phase_id) for entry in existing.section_rates}
        card[line.service_id] = engine.RateCardEntry(
            service_id=existing.service_id,
            service_code=existing.service_code,
            service_name=existing.service_name,
            provider_type=existing.provider_type,
            charging_basis=existing.charging_basis,
            afe_line_id=existing.afe_line_id,
            rates=merged_rates,
            per_service_amount=existing.per_service_amount or to_decimal(line.per_service_amount),
            section_rates=(
                *existing.section_rates,
                *(entry for entry in section_rates if (entry.section_id, entry.phase_id) not in seen),
            ),
            section_id=existing.section_id,
            phase_id=existing.phase_id,
        )
    return card


def rate_card_out(card: dict[int, engine.RateCardEntry]) -> list[RateCardServiceOut]:
    """Serialise the rate card for the page's pickers."""

    return [
        RateCardServiceOut(
            service_id=entry.service_id,
            afe_line_id=entry.afe_line_id,
            service_code=entry.service_code,
            service_name=entry.service_name,
            provider_type=entry.provider_type,
            charging_basis=entry.charging_basis,
            per_service_amount=entry.per_service_amount,
            section_id=entry.section_id,
            phase_id=entry.phase_id,
            rates=[{"category": category, "unit_rate": rate} for category, rate in entry.rates.items()],
            section_rates=[
                {"section_id": rate.section_id, "phase_id": rate.phase_id, "amount": rate.amount}
                for rate in entry.section_rates
            ],
        )
        for entry in sorted(card.values(), key=lambda item: (item.service_code, item.service_name))
    ]


def fuel_rate_from_afe(db: Session, afe: Afe | None) -> Decimal:
    """The fuel unit rate captured on the AFE cost estimate (0 when absent)."""

    if afe is None:
        return Decimal("0")
    line = db.scalar(
        select(AfeConsumableLine).where(
            AfeConsumableLine.afe_id == afe.id,
            AfeConsumableLine.item_kind == "fuel",
        )
    )
    if line is None:
        return Decimal("0")
    return effective_rate(line.captured_rate, line.override_rate)


# ---------------------------------------------------------------------------
# Read models
# ---------------------------------------------------------------------------


def build_entry_out(entry: DailyCostEntry) -> DailyCostEntryOut:
    """The day's header row with its three group totals."""

    rig = entry.rig
    well = entry.well
    services, consumables, tangibles = entry_totals(entry)
    rig_code = rig.rig_code if rig else None
    rig_name = rig.rig_name if rig else None
    well_code = well.well_code if well else None
    well_name = well.well_name if well else None
    return DailyCostEntryOut(
        id=entry.id,
        daily_cost_code=entry.daily_cost_code or "",
        rig_id=entry.rig_id,
        well_id=entry.well_id,
        cost_date=entry.cost_date,
        afe_id=entry.afe_id,
        afe_code=afe_code_of(entry),
        remarks=entry.remarks,
        status=entry.status or "draft",
        submitted_at=entry.submitted_at,
        reconciliation_status=entry.reconciliation_status or "pending",
        reconciliation_ref=entry.reconciliation_ref,
        reconciled_at=entry.reconciled_at,
        is_deleted=entry.is_deleted,
        deleted_at=entry.deleted_at,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        rig_code=rig_code,
        rig_name=rig_name,
        rig_display=_display(rig_code, rig_name),
        well_code=well_code,
        well_name=well_name,
        well_display=_display(well_code, well_name),
        service_count=len(entry.service_lines),
        consumable_count=len(entry.consumable_lines),
        tangible_count=len(entry.tangible_lines),
        service_total=services,
        consumable_total=consumables,
        tangible_total=tangibles,
        total_cost=money(services + consumables + tangibles),
    )


def _service_line_out(line: DailyCostServiceLine) -> DailyServiceLineOut:
    service = line.service
    return DailyServiceLineOut(
        id=line.id,
        service_id=line.service_id,
        service_code=service.service_code if service else None,
        service_name=service.service_name if service else None,
        provider_type=service.provider_type if service else None,
        afe_line_id=line.afe_line_id,
        charging_basis=line.charging_basis,
        charge_category=line.charge_category,
        section_id=line.section_id,
        phase_id=line.phase_id,
        sub_activity_id=line.sub_activity_id,
        sub_activity_display=_sub_activity_display(line),
        quantity=to_decimal(line.quantity),
        quantity_unit=line.quantity_unit or UNIT_HOURS,
        captured_rate=to_decimal(line.captured_rate),
        override_rate=None if line.override_rate is None else to_decimal(line.override_rate),
        amount=to_decimal(line.amount),
        remarks=line.remarks,
    )


def _consumable_line_out(line: DailyCostConsumableLine) -> DailyConsumableLineOut:
    return DailyConsumableLineOut(
        id=line.id,
        category=line.category,
        item_id=line.item_id,
        item_code=line.item_code,
        item_name=line.item_name,
        quantity=to_decimal(line.quantity),
        uom=line.uom,
        currency=line.currency,
        captured_rate=to_decimal(line.captured_rate),
        override_rate=None if line.override_rate is None else to_decimal(line.override_rate),
        manual_amount=None if line.manual_amount is None else to_decimal(line.manual_amount),
        amount=to_decimal(line.amount),
        section_id=line.section_id,
        phase_id=line.phase_id,
        sub_activity_id=line.sub_activity_id,
        sub_activity_display=_sub_activity_display(line),
        remarks=line.remarks,
    )


def _tangible_line_out(line: DailyCostTangibleLine) -> DailyTangibleLineOut:
    tangible = line.tangible
    return DailyTangibleLineOut(
        id=line.id,
        tangible_id=line.tangible_id,
        tangible_code=tangible.tangible_code if tangible else None,
        tangible_name=tangible.tangible_name if tangible else None,
        quantity=to_decimal(line.quantity),
        uom=line.uom,
        currency=line.currency,
        captured_rate=to_decimal(line.captured_rate),
        override_rate=None if line.override_rate is None else to_decimal(line.override_rate),
        amount=to_decimal(line.amount),
        remarks=line.remarks,
    )


def _summary(services: Decimal, consumables: Decimal, tangibles: Decimal) -> list[dict[str, Any]]:
    return [
        {"group": GROUP_SERVICES, "amount": services},
        {"group": GROUP_CONSUMABLES, "amount": consumables},
        {"group": GROUP_TANGIBLES, "amount": tangibles},
        {"group": "Total", "amount": money(services + consumables + tangibles)},
    ]


def build_day_out(
    entry: DailyCostEntry, extra_warnings: Sequence[str] | None = None
) -> DailyCostDayOut:
    """The full read model of one day, with live warnings from the engine.

    ``extra_warnings`` carries the rate/scope notes the normaliser produced
    while saving — they are about how the rates were resolved, so the engine
    does not repeat them when it prices the stored lines.
    """

    well: Well | None = entry.well
    estimate = compile_entry(entry)
    services, consumables, tangibles = entry_totals(entry)
    return DailyCostDayOut(
        entry=build_entry_out(entry),
        well_configuration=build_configuration_out(well) if well else None,
        services=[_service_line_out(line) for line in entry.service_lines],
        consumables=[_consumable_line_out(line) for line in entry.consumable_lines],
        tangibles=[_tangible_line_out(line) for line in entry.tangible_lines],
        summary=_summary(services, consumables, tangibles),
        grand_total=money(services + consumables + tangibles),
        warnings=list(dict.fromkeys([*estimate.totals.warnings, *(extra_warnings or [])])),
    )


# ---------------------------------------------------------------------------
# Engine bridge
# ---------------------------------------------------------------------------


def compile_entry(entry: DailyCostEntry) -> engine.DailyCostEstimate:
    """Price the persisted lines of one day (used for the live warnings)."""

    return engine.compile_daily_cost(
        service_lines=[
            engine.DailyServiceLine(
                line_id=line.id,
                service_id=line.service_id,
                service_code=line.service.service_code if line.service else "",
                service_name=line.service.service_name if line.service else "",
                provider_type=line.service.provider_type if line.service else "",
                charging_basis=line.charging_basis,
                charge_category=line.charge_category,
                section_id=line.section_id,
                phase_id=line.phase_id,
                sub_activity_id=line.sub_activity_id,
                quantity=to_decimal(line.quantity),
                quantity_unit=line.quantity_unit or UNIT_HOURS,
                captured_rate=to_decimal(line.captured_rate),
                override_rate=None if line.override_rate is None else to_decimal(line.override_rate),
                remarks=line.remarks,
            )
            for line in entry.service_lines
        ],
        consumable_lines=[
            engine.DailyConsumableLine(
                line_id=line.id,
                category=line.category,
                item_id=line.item_id,
                item_code=line.item_code,
                item_name=line.item_name,
                quantity=to_decimal(line.quantity),
                captured_rate=to_decimal(line.captured_rate),
                override_rate=None if line.override_rate is None else to_decimal(line.override_rate),
                manual_amount=None if line.manual_amount is None else to_decimal(line.manual_amount),
                uom=line.uom,
                currency=line.currency,
                section_id=line.section_id,
                phase_id=line.phase_id,
                sub_activity_id=line.sub_activity_id,
                remarks=line.remarks,
            )
            for line in entry.consumable_lines
        ],
        tangible_lines=[
            engine.DailyTangibleLine(
                line_id=line.id,
                tangible_id=line.tangible_id,
                tangible_code=line.tangible.tangible_code if line.tangible else "",
                tangible_name=line.tangible.tangible_name if line.tangible else "",
                quantity=to_decimal(line.quantity),
                captured_rate=to_decimal(line.captured_rate),
                override_rate=None if line.override_rate is None else to_decimal(line.override_rate),
                uom=line.uom,
                currency=line.currency,
                remarks=line.remarks,
            )
            for line in entry.tangible_lines
        ],
    )


def _domain_lines(
    services: list[dict[str, Any]],
    consumables: list[dict[str, Any]],
    tangibles: list[dict[str, Any]],
) -> tuple[
    list[engine.DailyServiceLine],
    list[engine.DailyConsumableLine],
    list[engine.DailyTangibleLine],
]:
    return (
        [
            engine.DailyServiceLine(
                line_id=row.get("line_id"),
                service_id=row["service_id"],
                service_code=row.get("service_code", ""),
                service_name=row.get("service_name", ""),
                provider_type=row.get("provider_type", ""),
                charging_basis=row["charging_basis"],
                charge_category=row["charge_category"],
                section_id=row["section_id"],
                phase_id=row["phase_id"],
                sub_activity_id=row["sub_activity_id"],
                quantity=row["quantity"],
                quantity_unit=row["quantity_unit"],
                captured_rate=row["captured_rate"],
                override_rate=row["override_rate"],
                remarks=row["remarks"],
            )
            for row in services
        ],
        [
            engine.DailyConsumableLine(
                line_id=row.get("line_id"),
                category=row["category"],
                item_id=row["item_id"],
                item_code=row["item_code"],
                item_name=row["item_name"],
                quantity=row["quantity"],
                captured_rate=row["captured_rate"],
                override_rate=row["override_rate"],
                manual_amount=row["manual_amount"],
                uom=row["uom"],
                currency=row["currency"],
                section_id=row["section_id"],
                phase_id=row["phase_id"],
                sub_activity_id=row["sub_activity_id"],
                remarks=row["remarks"],
            )
            for row in consumables
        ],
        [
            engine.DailyTangibleLine(
                line_id=row.get("line_id"),
                tangible_id=row["tangible_id"],
                tangible_code=row.get("tangible_code", ""),
                tangible_name=row.get("tangible_name", ""),
                quantity=row["quantity"],
                captured_rate=row["captured_rate"],
                override_rate=row["override_rate"],
                uom=row["uom"],
                currency=row["currency"],
                remarks=row["remarks"],
            )
            for row in tangibles
        ],
    )


# ---------------------------------------------------------------------------
# Normalisation (rate capture + scope validation)
# ---------------------------------------------------------------------------


def _check_well(db: Session, well_id: int) -> Well:
    well = db.get(Well, well_id)
    if not well or well.is_deleted:
        raise DailyCostValidationError("Well not found or deleted")
    return well


def _resolve_afe(db: Session, afe_id: int | None, well: Well) -> Afe | None:
    if afe_id is None:
        return None
    # with_estimate_lines=True because the rate card reads the AFE's service
    # lines (and the fuel rate reads its consumable lines).
    afe = load_afe(db, afe_id, with_estimate_lines=True)
    if afe is None or afe.is_deleted:
        raise DailyCostValidationError("The selected AFE does not exist any more")
    if afe.well_id != well.id:
        raise DailyCostValidationError("The selected AFE belongs to another well")
    return afe


def _check_sub_activity(db: Session, sub_activity_id: int | None, well: Well) -> int | None:
    if sub_activity_id is None:
        return None
    record = db.get(WellSubActivity, sub_activity_id)
    if record is None or record.is_deleted:
        raise DailyCostValidationError("The selected Well Sub Activity does not exist any more")
    if record.well_id != well.id:
        raise DailyCostValidationError(
            "The selected Well Sub Activity belongs to another well — pick one of this well's sub activities"
        )
    return record.id


def _scope_warnings(well: Well, section_id: int | None, phase_id: int | None) -> list[str]:
    """Warn (never fail) when a recorded scope left the well configuration."""

    scope = build_well_scope(well)
    warnings: list[str] = []
    if section_id is not None and scope.find_section(section_id) is None:
        warnings.append("the section is no longer part of the well configuration")
    if phase_id is not None and not scope.has_phase(section_id, phase_id):
        warnings.append("the phase is no longer part of the well configuration")
    return warnings


def _normalize_service(
    db: Session,
    well: Well,
    card: dict[int, engine.RateCardEntry],
    row: Any,
    warnings: list[str],
) -> dict[str, Any]:
    service = db.get(Service, row.service_id)
    if service is None or service.is_deleted:
        raise DailyCostValidationError("The selected service does not exist any more")

    section_id = row.section_id
    phase_id = row.phase_id
    sub_activity_id = _check_sub_activity(db, row.sub_activity_id, well)
    for warning in _scope_warnings(well, section_id, phase_id):
        warnings.append(f"{service.service_code}: {warning}")

    entry = card.get(service.id)
    override_rate = row.override_rate
    if entry is not None:
        basis = normalize_basis(entry.charging_basis)
        afe_line_id = entry.afe_line_id
        if basis == BASIS_DAILY:
            try:
                category = normalize_category(row.charge_category or "Operation")
            except ValueError as exc:
                raise DailyCostValidationError(f"{service.service_code}: {exc}") from exc
            captured = entry.rate_for(category)
        elif basis == BASIS_PER_SERVICE:
            category = BASIS_PER_SERVICE
            captured = entry.per_service_amount
        else:
            category = BASIS_PER_SECTION
            if section_id is None:
                raise DailyCostValidationError(
                    f"{service.service_code} is charged per section — select the section"
                )
            captured = entry.section_amount(section_id, phase_id)
            if captured == 0:
                warnings.append(
                    f"{service.service_code}: the AFE has no rate for this section"
                    " — enter an override unit rate"
                )
    else:
        # Not on the AFE: the user enters the rate by hand (override or manual).
        basis = normalize_basis(row.charging_basis or BASIS_DAILY)
        afe_line_id = None
        if basis == BASIS_DAILY:
            try:
                category = normalize_category(row.charge_category or "Operation")
            except ValueError as exc:
                raise DailyCostValidationError(f"{service.service_code}: {exc}") from exc
        else:
            category = basis
        captured = to_decimal(row.captured_rate)
        warnings.append(
            f"{service.service_code} is not on the selected AFE — its rate was entered manually"
        )

    unit = row.quantity_unit or UNIT_HOURS
    quantity = to_decimal(row.quantity)
    if quantity < 0:
        raise DailyCostValidationError(f"{service.service_code}: operating quantity cannot be negative")
    limit = engine.MAX_HOURS if unit == UNIT_HOURS else engine.MAX_DAYS
    if quantity > limit:
        label = "hours (0-24)" if unit == UNIT_HOURS else "days (0-1)"
        raise DailyCostValidationError(
            f"{service.service_code}: operating quantity must be entered in {label}"
        )

    return {
        "service_id": service.id,
        "service_code": service.service_code,
        "service_name": service.service_name,
        "provider_type": service.provider_type,
        "afe_line_id": afe_line_id,
        "charging_basis": basis,
        "charge_category": category,
        "section_id": section_id,
        "phase_id": phase_id,
        "sub_activity_id": sub_activity_id,
        "quantity": quantity,
        "quantity_unit": unit,
        "captured_rate": captured,
        "override_rate": None if override_rate is None else to_decimal(override_rate),
        "remarks": row.remarks,
    }


def _normalize_consumable(
    db: Session,
    well: Well,
    afe: Afe | None,
    row: Any,
    warnings: list[str],
) -> dict[str, Any]:
    category = engine.normalize_consumable_category(row.category)
    sub_activity_id = _check_sub_activity(db, row.sub_activity_id, well)
    for warning in _scope_warnings(well, row.section_id, row.phase_id):
        warnings.append(f"{row.item_code or category}: {warning}")

    quantity = to_decimal(row.quantity)
    override_rate = None if row.override_rate is None else to_decimal(row.override_rate)
    manual_amount = None if row.manual_amount is None else to_decimal(row.manual_amount)
    uom = row.uom
    currency = row.currency
    item_id: int | None = row.item_id

    if category == engine.MUD_CHEMICAL:
        if item_id is None:
            raise DailyCostValidationError("Select the mud chemical that was consumed")
        chemical = db.get(MudChemical, item_id)
        if chemical is None or chemical.is_deleted:
            raise DailyCostValidationError("The selected mud chemical does not exist any more")
        item_code, item_name = chemical.chemical_code, chemical.chemical_name
        captured = to_decimal(chemical.current_rate)
        uom = uom or chemical.uom
        currency = currency or chemical.currency
    elif category == engine.DRILL_BIT:
        if item_id is None:
            raise DailyCostValidationError("Select the drill bit that was used")
        bit = db.get(DrillBit, item_id)
        if bit is None or bit.is_deleted:
            raise DailyCostValidationError("The selected drill bit does not exist any more")
        item_code, item_name = bit.bit_code, bit.bit_name
        captured = to_decimal(bit.final_cost)
        uom = uom or "each"
        currency = currency or bit.currency
    elif category == engine.FUEL:
        item_id = None
        item_code = str(row.item_code or FUEL_CODE)
        item_name = str(row.item_name or FUEL_NAME)
        captured = fuel_rate_from_afe(db, afe)
        uom = uom or "LTR"
        if captured == 0 and override_rate is None:
            warnings.append(
                "Fuel has no unit rate on the AFE cost estimate — enter an override unit rate"
            )
    else:  # cement additives: a manual total for the chosen scope
        item_id = None
        item_code = str(row.item_code or CEMENT_CODE)
        item_name = str(row.item_name or CEMENT_NAME)
        captured = Decimal("0")
        if manual_amount is None or manual_amount == 0:
            warnings.append("Cement additives: enter the total consumption cost for the day")

    return {
        "category": category,
        "item_id": item_id,
        "item_code": item_code or category,
        "item_name": item_name or category,
        "quantity": quantity,
        "uom": uom,
        "currency": currency,
        "captured_rate": captured,
        "override_rate": override_rate,
        "manual_amount": manual_amount,
        "section_id": row.section_id,
        "phase_id": row.phase_id,
        "sub_activity_id": sub_activity_id,
        "remarks": row.remarks,
    }


def _normalize_tangible(db: Session, row: Any, warnings: list[str]) -> dict[str, Any]:
    tangible = db.get(Tangible, row.tangible_id)
    if tangible is None or tangible.is_deleted:
        raise DailyCostValidationError("The selected tangible does not exist any more")
    captured = to_decimal(row.captured_rate) if row.captured_rate is not None else to_decimal(tangible.final_cost)
    if captured == 0 and row.override_rate is None:
        warnings.append(f"{tangible.tangible_code} has no unit rate in Master Data — enter an override rate")
    return {
        "tangible_id": tangible.id,
        "tangible_code": tangible.tangible_code,
        "tangible_name": tangible.tangible_name,
        "quantity": to_decimal(row.quantity),
        "uom": row.uom or tangible.uom,
        "currency": row.currency or tangible.currency,
        "captured_rate": captured,
        "override_rate": None if row.override_rate is None else to_decimal(row.override_rate),
        "remarks": row.remarks,
    }


def normalize_day(
    db: Session,
    well: Well,
    afe: Afe | None,
    payload: DailyCostSaveIn,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    """Resolve every rate and scope of a payload (no money maths here)."""

    warnings: list[str] = []
    card = build_rate_card(db, afe)
    services = [_normalize_service(db, well, card, row, warnings) for row in payload.services]
    consumables = [_normalize_consumable(db, well, afe, row, warnings) for row in payload.consumables]
    tangibles = [_normalize_tangible(db, row, warnings) for row in payload.tangibles]
    return services, consumables, tangibles, warnings


# ---------------------------------------------------------------------------
# Preview / save
# ---------------------------------------------------------------------------


def _price_rows(
    services: list[dict[str, Any]],
    consumables: list[dict[str, Any]],
    tangibles: list[dict[str, Any]],
) -> None:
    """Price every normalised row with the engine and store it on the row.

    The engine is the only place money is calculated; a rule violation here is
    always a data problem (an unknown category, a quantity outside its range),
    so it surfaces as a validation error instead of a 500.
    """

    for row in services:
        try:
            row["amount"] = engine.service_amount(
                charging_basis=row["charging_basis"],
                charge_category=row["charge_category"],
                quantity=row["quantity"],
                quantity_unit=row["quantity_unit"],
                captured_rate=row["captured_rate"],
                override_rate=row["override_rate"],
            )
        except ValueError as exc:
            raise DailyCostValidationError(f"{row['service_code']}: {exc}") from exc
    for row in consumables:
        try:
            row["amount"] = engine.consumable_amount(
                category=row["category"],
                quantity=row["quantity"],
                captured_rate=row["captured_rate"],
                override_rate=row["override_rate"],
                manual_amount=row["manual_amount"],
            )
        except ValueError as exc:
            raise DailyCostValidationError(f"{row['item_code']}: {exc}") from exc
    for row in tangibles:
        row["amount"] = engine.tangible_amount(
            quantity=row["quantity"],
            captured_rate=row["captured_rate"],
            override_rate=row["override_rate"],
        )


def preview_day(
    db: Session, well: Well, afe: Afe | None, payload: DailyCostSaveIn
) -> dict[str, Any]:
    """Price an unsaved day with the same engine the save uses.

    Nothing is written: the daily page calls this (debounced) so the totals on
    screen are produced by the server, never by the browser.
    """

    services, consumables, tangibles, warnings = normalize_day(db, well, afe, payload)
    service_lines, consumable_lines, tangible_lines = _domain_lines(services, consumables, tangibles)
    estimate = engine.compile_daily_cost(service_lines, consumable_lines, tangible_lines)

    def rows(results: tuple[engine.LineResult, ...]) -> list[dict[str, Any]]:
        return [
            {
                "line_id": result.line_id,
                "code": result.code,
                "name": result.name,
                "amount": result.amount,
                "warnings": list(result.warnings),
            }
            for result in results
        ]

    totals = estimate.totals
    return {
        "services": rows(estimate.service_lines),
        "consumables": rows(estimate.consumable_lines),
        "tangibles": rows(estimate.tangible_lines),
        "summary": _summary(totals.services, totals.consumables, totals.tangibles),
        "grand_total": totals.total,
        "warnings": list(dict.fromkeys([*totals.warnings, *warnings])),
    }


def _clear_lines(entry: DailyCostEntry) -> None:
    entry.service_lines.clear()
    entry.consumable_lines.clear()
    entry.tangible_lines.clear()


def save_day(
    db: Session, entry: DailyCostEntry, payload: DailyCostSaveIn, user: User
) -> DailyCostDayOut:
    """Validate and replace the whole day, then price it with the engine."""

    ensure_draft(entry)
    well = _check_well(db, entry.well_id)
    afe = _resolve_afe(db, entry.afe_id, well)
    services, consumables, tangibles, save_warnings = normalize_day(db, well, afe, payload)
    _price_rows(services, consumables, tangibles)

    service_rows = [
        DailyCostServiceLine(
            service_id=row["service_id"],
            afe_line_id=row["afe_line_id"],
            charging_basis=row["charging_basis"],
            charge_category=row["charge_category"],
            section_id=row["section_id"],
            phase_id=row["phase_id"],
            sub_activity_id=row["sub_activity_id"],
            quantity=row["quantity"],
            quantity_unit=row["quantity_unit"],
            captured_rate=row["captured_rate"],
            override_rate=row["override_rate"],
            amount=row["amount"],
            remarks=row["remarks"],
            sort_order=index,
            created_by=user.id,
            updated_by=user.id,
        )
        for index, row in enumerate(services)
    ]
    consumable_rows = [
        DailyCostConsumableLine(
            category=row["category"],
            item_id=row["item_id"],
            item_code=row["item_code"],
            item_name=row["item_name"],
            quantity=row["quantity"],
            uom=row["uom"],
            currency=row["currency"],
            captured_rate=row["captured_rate"],
            override_rate=row["override_rate"],
            manual_amount=row["manual_amount"],
            amount=row["amount"],
            section_id=row["section_id"],
            phase_id=row["phase_id"],
            sub_activity_id=row["sub_activity_id"],
            remarks=row["remarks"],
            sort_order=index,
            created_by=user.id,
            updated_by=user.id,
        )
        for index, row in enumerate(consumables)
    ]
    tangible_rows = [
        DailyCostTangibleLine(
            tangible_id=row["tangible_id"],
            quantity=row["quantity"],
            uom=row["uom"],
            currency=row["currency"],
            captured_rate=row["captured_rate"],
            override_rate=row["override_rate"],
            amount=row["amount"],
            remarks=row["remarks"],
            sort_order=index,
            created_by=user.id,
            updated_by=user.id,
        )
        for index, row in enumerate(tangibles)
    ]

    with _DAY_SAVE_LOCK:
        db.execute(select(DailyCostEntry.id).where(DailyCostEntry.id == entry.id).with_for_update())
        db.expire(entry, ["status", "service_lines", "consumable_lines", "tangible_lines"])
        ensure_draft(entry)
        _clear_lines(entry)
        entry.service_lines.extend(service_rows)
        entry.consumable_lines.extend(consumable_rows)
        entry.tangible_lines.extend(tangible_rows)
        if "remarks" in payload.model_fields_set:
            entry.remarks = payload.remarks
        entry.updated_by = user.id
        db.commit()
        db.refresh(entry)
        db.expire(entry, ["service_lines", "consumable_lines", "tangible_lines"])
        return build_day_out(entry, extra_warnings=save_warnings)


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------


def ensure_draft(entry: DailyCostEntry) -> None:
    if entry.status != engine.STATUS_DRAFT:
        raise DailyCostValidationError(
            f"Daily cost {entry.daily_cost_code} is {entry.status} — reopen it as draft before editing."
        )


def change_status(
    db: Session, entry: DailyCostEntry, action: str, remarks: str | None, user: User
) -> tuple[DailyCostEntry, str]:
    """Move a day between draft and submitted, with remarks."""

    note = (remarks or "").strip()
    if not note:
        raise DailyCostValidationError("Remarks are required for a status change")

    if action == "submit":
        if entry.status != engine.STATUS_DRAFT:
            raise DailyCostValidationError(f"Daily cost {entry.daily_cost_code} is already submitted")
        if not (entry.service_lines or entry.consumable_lines or entry.tangible_lines):
            raise DailyCostValidationError(
                "Add at least one service, consumable or tangible before submitting the day"
            )
        entry.status = engine.STATUS_SUBMITTED
        entry.submitted_at = datetime.now(UTC)
        detail = f"Submitted daily cost {entry.daily_cost_code}"
    elif action == "reopen":
        if entry.status == engine.STATUS_DRAFT:
            raise DailyCostValidationError(f"Daily cost {entry.daily_cost_code} is already a draft")
        entry.status = engine.STATUS_DRAFT
        entry.submitted_at = None
        detail = f"Reopened daily cost {entry.daily_cost_code} back to draft"
    else:  # pragma: no cover - guarded by the Literal schema
        raise DailyCostValidationError(f"Unknown status action '{action}'")

    entry.remarks = note if action == "submit" else entry.remarks
    entry.updated_by = user.id
    db.commit()
    db.refresh(entry)
    return entry, f"{detail} — remarks: {note}"


# ---------------------------------------------------------------------------
# AFE side of the comparison (used by the analytics / reports services)
# ---------------------------------------------------------------------------


def afe_group_totals(db: Session, afe: Afe) -> dict[str, Decimal]:
    """The AFE estimate split per cost group."""

    estimate = compile_estimate(afe)
    return {
        GROUP_SERVICES: estimate.services.amount,
        GROUP_CONSUMABLES: estimate.consumables.amount,
        GROUP_TANGIBLES: estimate.tangibles.amount,
    }


def afe_section_totals(db: Session, afe: Afe) -> dict[int, Decimal]:
    """The AFE estimate attributed to each configured section."""

    del db
    estimate = compile_estimate(afe)
    return {
        row.section_id: to_decimal(row.amount)
        for row in estimate.by_section
        if row.section_id is not None
    }


# ---------------------------------------------------------------------------
# Export rows (the daily costs report)
# ---------------------------------------------------------------------------


EXPORT_HEADERS = [
    "daily_cost_code",
    "cost_date",
    "rig_code",
    "rig_name",
    "well_code",
    "well_name",
    "afe_code",
    "status",
    "cost_group",
    "category",
    "code",
    "name",
    "charging_basis",
    "section",
    "phase",
    "well_sub_activity",
    "quantity",
    "unit",
    "captured_rate",
    "override_rate",
    "amount",
    "remarks",
]


def _section_phase_labels(well: Well | None, section_id: int | None, phase_id: int | None) -> tuple[str, str]:
    if well is None:
        return ("", "")
    scope = build_well_scope(well)
    section = scope.find_section(section_id)
    section_label = section.label if section else ""
    phase_label = ""
    if phase_id is not None:
        code, name = scope.phase_code_and_name(phase_id)
        phase_label = scope_label(code, name) if (code or name) else ""
    return (section_label, phase_label)


def export_rows(db: Session, entries: list[DailyCostEntry]) -> list[list[Any]]:
    """Flatten every line of every day into report rows."""

    del db
    rows: list[list[Any]] = []
    for entry in entries:
        well = entry.well
        rig = entry.rig
        header = [
            entry.daily_cost_code,
            entry.cost_date.isoformat() if entry.cost_date else "",
            rig.rig_code if rig else "",
            rig.rig_name if rig else "",
            well.well_code if well else "",
            well.well_name if well else "",
            afe_code_of(entry) or "",
            entry.status,
        ]
        for line in entry.service_lines:
            section_label, phase_label = _section_phase_labels(well, line.section_id, line.phase_id)
            rows.append(
                [
                    *header,
                    GROUP_SERVICES,
                    line.charge_category,
                    line.service.service_code if line.service else "",
                    line.service.service_name if line.service else "",
                    line.charging_basis,
                    section_label,
                    phase_label,
                    _sub_activity_display(line) or "",
                    str(to_decimal(line.quantity)),
                    line.quantity_unit or UNIT_HOURS,
                    str(to_decimal(line.captured_rate)),
                    "" if line.override_rate is None else str(to_decimal(line.override_rate)),
                    str(to_decimal(line.amount)),
                    line.remarks or "",
                ]
            )
        for line in entry.consumable_lines:
            section_label, phase_label = _section_phase_labels(well, line.section_id, line.phase_id)
            rows.append(
                [
                    *header,
                    GROUP_CONSUMABLES,
                    engine.CONSUMABLE_CATEGORY_LABELS.get(line.category, line.category),
                    line.item_code,
                    line.item_name,
                    line.category,
                    section_label,
                    phase_label,
                    _sub_activity_display(line) or "",
                    str(to_decimal(line.quantity)),
                    line.uom or "",
                    str(to_decimal(line.captured_rate)),
                    "" if line.override_rate is None else str(to_decimal(line.override_rate)),
                    str(to_decimal(line.amount)),
                    line.remarks or "",
                ]
            )
        for line in entry.tangible_lines:
            rows.append(
                [
                    *header,
                    GROUP_TANGIBLES,
                    "Tangible",
                    line.tangible.tangible_code if line.tangible else "",
                    line.tangible.tangible_name if line.tangible else "",
                    "",
                    "",
                    "",
                    "",
                    str(to_decimal(line.quantity)),
                    line.uom or "",
                    str(to_decimal(line.captured_rate)),
                    "" if line.override_rate is None else str(to_decimal(line.override_rate)),
                    str(to_decimal(line.amount)),
                    line.remarks or "",
                ]
            )
    return rows
