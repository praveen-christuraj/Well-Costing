"""AFE cost estimation workflow.

Everything the AFE Cost Estimation tab needs, minus the HTTP:

* reading the AFE's lines + the well configuration and running them through the
  framework-free engine in :mod:`app.domain.afe_costing`;
* validating and persisting a whole estimate atomically;
* flattening an estimate into export rows.

The routes stay thin and translate :class:`AfeValidationError` into HTTP 400s.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.domain import afe_costing as engine
from app.models.afe import (
    Afe,
    AfeConsumableLine,
    AfeServiceChargeLine,
    AfeServiceLine,
    AfeServiceRate,
    AfeServiceSectionRate,
    AfeTangibleLine,
)
from app.models.catalogue import DrillBit, MudChemical, Service, Tangible
from app.models.rig_well import Well
from app.models.user import User
from app.schemas.afe import (
    AfeEstimateOut,
    AfeOut,
    ConsumableLineOut,
    CostComponentOut,
    EstimateIn,
    GroupSummaryOut,
    LineEstimateOut,
    SectionRollupOut,
    ServiceLineOut,
    TangibleLineOut,
)
from app.services.well_configuration import build_configuration_out


class AfeValidationError(ValueError):
    """Raised for anything the user must fix before an estimate can be saved."""


# ---------------------------------------------------------------------------
# AFE header read model
# ---------------------------------------------------------------------------


def build_afe_out(afe: Afe, estimate: engine.AfeEstimate | None = None) -> AfeOut:
    """AFE header row: rig/well labels, line counts and the estimated total."""

    rig = afe.rig
    well = afe.well
    rig_code = rig.rig_code if rig else None
    rig_name = rig.rig_name if rig else None
    well_code = well.well_code if well else None
    well_name = well.well_name if well else None
    if estimate is None:
        estimate = compile_estimate(afe)
    return AfeOut(
        id=afe.id,
        afe_code=afe.afe_code or "",
        afe_name=afe.afe_name or "",
        afe_type=afe.afe_type or "Drilling",
        rig_id=afe.rig_id,
        well_id=afe.well_id,
        remarks=afe.remarks,
        status=afe.status or "draft",
        status_remarks=afe.status_remarks,
        submitted_at=afe.submitted_at,
        approved_at=afe.approved_at,
        is_deleted=afe.is_deleted,
        deleted_at=afe.deleted_at,
        created_at=afe.created_at,
        updated_at=afe.updated_at,
        rig_code=rig_code,
        rig_name=rig_name,
        rig_display=f"{rig_code} - {rig_name}" if rig_code and rig_name else (rig_code or rig_name),
        well_code=well_code,
        well_name=well_name,
        well_display=f"{well_code} - {well_name}" if well_code and well_name else (well_code or well_name),
        service_count=len(afe.service_lines),
        consumable_count=len(afe.consumable_lines),
        tangible_count=len(afe.tangible_lines),
        estimated_total=estimate.total,
    )


# ---------------------------------------------------------------------------
# Well configuration -> engine scope
# ---------------------------------------------------------------------------


def build_well_scope(well: Well) -> engine.WellScope:
    """Snapshot the well configuration the AFE is estimated against."""

    sections: list[engine.WellSectionScope] = []
    for section in well.sections:
        phases = tuple(
            engine.WellPhaseScope(
                phase_id=phase.phase_id,
                phase_code=phase.phase.phase_code if phase.phase else None,
                phase_name=phase.phase.phase_name if phase.phase else None,
                days=Decimal(phase.days or 0),
            )
            for phase in section.phases
        )
        sections.append(
            engine.WellSectionScope(
                section_id=section.section_id,
                section_code=section.section.section_code if section.section else None,
                section_name=section.section.section_name if section.section else None,
                from_depth=Decimal(section.from_depth or 0),
                to_depth=Decimal(section.to_depth or 0),
                phases=phases,
            )
        )
    return engine.WellScope(
        well_code=well.well_code or "",
        well_name=well.well_name or "",
        depth_unit=well.depth_unit or "m",
        sections=tuple(sections),
    )


def compile_estimate(afe: Afe) -> engine.AfeEstimate:
    """Run the AFE's configured lines through the calculation engine."""

    well = afe.well
    scope = build_well_scope(well) if well else engine.WellScope()

    services = [
        engine.ServiceLine(
            line_id=line.id,
            service_id=line.service_id,
            service_code=line.service.service_code if line.service else "",
            service_name=line.service.service_name if line.service else "",
            provider_type=line.service.provider_type if line.service else "",
            charging_basis=line.charging_basis,
            rates={rate.category: Decimal(rate.unit_rate or 0) for rate in line.rates},
            charge_lines=tuple(
                engine.ChargeLine(
                    category=charge.category,
                    quantity=Decimal(charge.quantity or 0),
                    unit=charge.quantity_unit or engine.UNIT_DAYS,
                )
                for charge in line.charge_lines
            ),
            section_rates=tuple(
                engine.SectionRate(
                    section_id=entry.section_id,
                    phase_id=entry.phase_id,
                    amount=Decimal(entry.amount or 0),
                )
                for entry in line.section_rates
            ),
            per_service_amount=Decimal(line.per_service_amount or 0),
            section_id=line.section_id,
            phase_id=line.phase_id,
            effective_date=line.effective_date,
            remarks=line.remarks,
        )
        for line in afe.service_lines
    ]
    consumables = [
        engine.ConsumableLine(
            line_id=line.id,
            item_id=line.item_id,
            item_code=line.item_code,
            item_name=line.item_name,
            item_kind=line.item_kind,
            quantity=Decimal(line.quantity or 0),
            captured_rate=Decimal(line.captured_rate or 0),
            override_rate=None if line.override_rate is None else Decimal(line.override_rate),
            uom=line.uom,
            currency=line.currency,
            section_id=line.section_id,
            phase_id=line.phase_id,
        )
        for line in afe.consumable_lines
    ]
    tangibles = [
        engine.TangibleLine(
            line_id=line.id,
            tangible_id=line.tangible_id,
            tangible_code=line.tangible.tangible_code if line.tangible else "",
            tangible_name=line.tangible.tangible_name if line.tangible else "",
            quantity=Decimal(line.quantity or 0),
            captured_rate=Decimal(line.captured_rate or 0),
            override_rate=None if line.override_rate is None else Decimal(line.override_rate),
            uom=line.uom,
            currency=line.currency,
        )
        for line in afe.tangible_lines
    ]
    return engine.compile_afe_estimate(scope, services, consumables, tangibles)


# ---------------------------------------------------------------------------
# Serialisation of the estimate
# ---------------------------------------------------------------------------


def _line_estimate_out(line: engine.LineEstimate) -> LineEstimateOut:
    return LineEstimateOut(
        amount=line.amount,
        components=[
            CostComponentOut(
                category=component.category,
                description=component.description,
                quantity=component.quantity,
                rate=component.rate,
                unit=component.unit,
                amount=component.amount,
                section_label=component.section_label,
                phase_label=component.phase_label,
            )
            for component in line.components
        ],
        warnings=list(line.warnings),
    )


def _estimate_for(lines: tuple[engine.LineEstimate, ...], line_id: int) -> LineEstimateOut:
    for line in lines:
        if line.line_id == line_id:
            return _line_estimate_out(line)
    return LineEstimateOut(amount=Decimal("0"))


def build_estimate_out(afe: Afe) -> AfeEstimateOut:
    """The full read model for one AFE's cost estimation."""

    estimate = compile_estimate(afe)
    well: Well | None = afe.well
    services = [
        ServiceLineOut(
            id=line.id,
            service_id=line.service_id,
            service_code=line.service.service_code if line.service else None,
            service_name=line.service.service_name if line.service else None,
            provider_type=line.service.provider_type if line.service else None,
            charging_basis=line.charging_basis,
            section_id=line.section_id,
            phase_id=line.phase_id,
            per_service_amount=Decimal(line.per_service_amount or 0),
            effective_date=line.effective_date,
            remarks=line.remarks,
            rates=[
                {"category": rate.category, "unit_rate": Decimal(rate.unit_rate or 0)}
                for rate in line.rates
            ],
            charge_lines=[
                {
                    "category": charge.category,
                    "quantity": Decimal(charge.quantity or 0),
                    "quantity_unit": charge.quantity_unit or "days",
                }
                for charge in line.charge_lines
            ],
            section_rates=[
                {
                    "section_id": entry.section_id,
                    "phase_id": entry.phase_id,
                    "amount": Decimal(entry.amount or 0),
                }
                for entry in line.section_rates
            ],
            estimate=_estimate_for(estimate.services.lines, line.id),
        )
        for line in afe.service_lines
    ]
    consumables = [
        ConsumableLineOut(
            id=line.id,
            item_kind=line.item_kind,
            item_id=line.item_id,
            item_code=line.item_code,
            item_name=line.item_name,
            quantity=Decimal(line.quantity or 0),
            captured_rate=Decimal(line.captured_rate or 0),
            override_rate=None if line.override_rate is None else Decimal(line.override_rate),
            uom=line.uom,
            currency=line.currency,
            section_id=line.section_id,
            phase_id=line.phase_id,
            remarks=line.remarks,
            estimate=_estimate_for(estimate.consumables.lines, line.id),
        )
        for line in afe.consumable_lines
    ]
    tangibles = [
        TangibleLineOut(
            id=line.id,
            tangible_id=line.tangible_id,
            tangible_code=line.tangible.tangible_code if line.tangible else None,
            tangible_name=line.tangible.tangible_name if line.tangible else None,
            quantity=Decimal(line.quantity or 0),
            captured_rate=Decimal(line.captured_rate or 0),
            override_rate=None if line.override_rate is None else Decimal(line.override_rate),
            uom=line.uom,
            currency=line.currency,
            remarks=line.remarks,
            estimate=_estimate_for(estimate.tangibles.lines, line.id),
        )
        for line in afe.tangible_lines
    ]
    return AfeEstimateOut(
        afe=build_afe_out(afe, estimate),
        well_configuration=build_configuration_out(well) if well else None,
        services=services,
        consumables=consumables,
        tangibles=tangibles,
        summary=[
            GroupSummaryOut(group=group.group, amount=group.amount, line_count=group.line_count)
            for group in estimate.groups
        ],
        by_section=[
            SectionRollupOut(
                section_id=row.section_id,
                section_label=row.section_label,
                planned_days=row.planned_days,
                amount=row.amount,
            )
            for row in estimate.by_section
        ],
        grand_total=estimate.total,
        warnings=list(estimate.warnings),
    )


# ---------------------------------------------------------------------------
# Master-data lookups used by validation
# ---------------------------------------------------------------------------


def resolve_service(db: Session, service_id: int) -> Service:
    service = db.get(Service, service_id)
    if not service or service.is_deleted:
        raise AfeValidationError(f"Service #{service_id} no longer exists in the master data")
    return service


def resolve_consumable(db: Session, kind: str, item_id: int | None) -> dict[str, Any]:
    """Look a consumable up in its master list or return category defaults."""

    if kind == "drill_bit":
        if item_id is None:
            raise AfeValidationError("Drill bit requires an item selection")
        item = db.get(DrillBit, item_id)
        if not item or item.is_deleted:
            raise AfeValidationError(f"Drill bit #{item_id} no longer exists in the master data")
        return {
            "item_code": item.bit_code,
            "item_name": item.bit_name,
            "captured_rate": Decimal(item.final_cost or 0),
            "uom": None,
            "currency": item.currency,
        }
    
    # For lump-sum categories, we just map the kind to a display name.
    lump_sums = {
        "mud_chemical": "Mud Chemicals",
        "cement_additive": "Cement Additives",
        "fuel": "Fuel"
    }
    if kind in lump_sums:
        return {
            "item_code": "LUMPSUM",
            "item_name": lump_sums[kind],
            "captured_rate": Decimal("0"),
            "uom": None,
            "currency": None,
        }

    raise AfeValidationError(f"Unknown consumable kind {kind}")


def resolve_tangible(db: Session, tangible_id: int) -> Tangible:
    tangible = db.get(Tangible, tangible_id)
    if not tangible or tangible.is_deleted:
        raise AfeValidationError(f"Tangible #{tangible_id} no longer exists in the master data")
    return tangible


# ---------------------------------------------------------------------------
# Saving an estimate
# ---------------------------------------------------------------------------


def ensure_draft(afe: Afe) -> None:
    """Only a draft AFE can be edited; the status lives on the estimate tab."""

    if afe.status != engine.STATUS_DRAFT:
        raise AfeValidationError(
            f"AFE {afe.afe_code} is {afe.status} — reopen it as Draft before editing the estimate."
        )


def _validate_scope(well_scope: engine.WellScope, section_id: int | None, phase_id: int | None, where: str) -> None:
    """Sections/phases must come from the well configuration, nothing else."""

    if section_id is not None and well_scope.find_section(section_id) is None:
        raise AfeValidationError(
            f"{where}: section is not part of the {well_scope.well_code or 'well'} configuration"
        )
    if phase_id is not None and not well_scope.has_phase(section_id, phase_id):
        raise AfeValidationError(f"{where}: phase is not part of the well configuration")


def _clear_lines(afe: Afe) -> None:
    """Remove the existing configuration rows through the ORM.

    Deleting each parent row (never a bulk ``Query.delete()``) keeps the
    ``rates`` / ``charge_lines`` / ``section_rates`` cascades working, so no
    orphaned child rows survive a re-save.
    """

    for line in list(afe.service_lines):
        afe.service_lines.remove(line)
    for line in list(afe.consumable_lines):
        afe.consumable_lines.remove(line)
    for line in list(afe.tangible_lines):
        afe.tangible_lines.remove(line)


def normalize_services(
    db: Session, payload: EstimateIn, well_scope: engine.WellScope
) -> list[dict[str, Any]]:
    """Validate the service lines and return them as plain, engine-ready dicts.

    One validation path serves both the save and the live preview, so the two
    can never disagree about what is allowed or what it costs.
    """

    seen: set[tuple[int, int | None, int | None]] = set()
    normalized: list[dict[str, Any]] = []
    for entry in payload.services:
        service = resolve_service(db, entry.service_id)
        where = f"Service {service.service_code}"
        key = (entry.service_id, entry.section_id, entry.phase_id)
        if key in seen:
            raise AfeValidationError(f"{where} is already added for the same section/phase scope")
        seen.add(key)
        _validate_scope(well_scope, entry.section_id, entry.phase_id, where)

        basis = engine.normalize_basis(entry.charging_basis)
        rates: dict[str, Decimal] = {}
        for rate in entry.rates:
            try:
                category = engine.normalize_category(rate.category)
            except ValueError as exc:
                raise AfeValidationError(f"{where}: {exc}") from exc
            if rate.unit_rate < 0:
                raise AfeValidationError(f"{where}: {category} rate cannot be negative")
            rates[category] = rate.unit_rate

        charge_rows: list[tuple[str, Decimal, str]] = []
        if basis == engine.BASIS_DAILY:
            for charge in entry.charge_lines:
                try:
                    category = engine.normalize_category(charge.category)
                    unit = engine.normalize_unit(charge.quantity_unit)
                except ValueError as exc:
                    raise AfeValidationError(f"{where}: {exc}") from exc
                if unit == engine.UNIT_HOURS and charge.quantity > Decimal("24"):
                    raise AfeValidationError(
                        f"{where}: {category} hours must be between 0 and 24 (use days for longer periods)"
                    )
                charge_rows.append((category, charge.quantity, unit))

        section_rows: list[tuple[int, int | None, Decimal]] = []
        if basis == engine.BASIS_PER_SECTION:
            if not entry.section_rates:
                raise AfeValidationError(f"{where}: add at least one section rate")
            for rate_entry in entry.section_rates:
                _validate_scope(
                    well_scope, rate_entry.section_id, rate_entry.phase_id, f"{where} section rate"
                )
                section_rows.append((rate_entry.section_id, rate_entry.phase_id, rate_entry.amount))

        if basis == engine.BASIS_PER_SERVICE and entry.per_service_amount <= 0:
            raise AfeValidationError(f"{where}: enter the per service price")

        normalized.append(
            {
                "service_id": entry.service_id,
                "service_code": service.service_code,
                "service_name": service.service_name,
                "provider_type": service.provider_type,
                "charging_basis": basis,
                "section_id": entry.section_id,
                "phase_id": entry.phase_id,
                "per_service_amount": entry.per_service_amount,
                "effective_date": entry.effective_date,
                "remarks": entry.remarks,
                "rates": rates,
                "charge_lines": charge_rows,
                "section_rates": section_rows,
            }
        )
    return normalized


def normalize_consumables(
    db: Session, payload: EstimateIn, well_scope: engine.WellScope
) -> list[dict[str, Any]]:
    """Validate the consumable lines against the master data and the well scope."""

    seen: set[tuple[str, int, int | None, int | None]] = set()
    normalized: list[dict[str, Any]] = []
    for index, entry in enumerate(payload.consumables, start=1):
        where = f"Consumable #{index}"
        if entry.section_id is None and entry.phase_id is None:
            raise AfeValidationError(f"{where}: select the section and/or phase it is estimated for")
        _validate_scope(well_scope, entry.section_id, entry.phase_id, where)
        key = (entry.item_kind, entry.item_id, entry.section_id, entry.phase_id)
        if key in seen:
            raise AfeValidationError(f"{where} is already estimated for the same section/phase scope")
        seen.add(key)
        master = resolve_consumable(db, entry.item_kind, entry.item_id)
        normalized.append(
            {
                "item_kind": entry.item_kind,
                "item_id": entry.item_id if entry.item_id is not None else 0,
                "item_code": str(master["item_code"]),
                "item_name": str(master["item_name"]),
                "quantity": entry.quantity,
                "captured_rate": Decimal(master["captured_rate"]),
                "override_rate": entry.override_rate,
                "uom": entry.uom or master.get("uom"),
                "currency": entry.currency or master.get("currency"),
                "section_id": entry.section_id,
                "phase_id": entry.phase_id,
                "remarks": entry.remarks,
            }
        )
    return normalized


def normalize_tangibles(db: Session, payload: EstimateIn) -> list[dict[str, Any]]:
    """Validate the tangible lines and capture their master-data rates."""

    seen: set[int] = set()
    normalized: list[dict[str, Any]] = []
    for entry in payload.tangibles:
        if entry.tangible_id in seen:
            raise AfeValidationError(f"Tangible #{entry.tangible_id} is already added to this AFE")
        seen.add(entry.tangible_id)
        tangible = resolve_tangible(db, entry.tangible_id)
        normalized.append(
            {
                "tangible_id": entry.tangible_id,
                "tangible_code": tangible.tangible_code,
                "tangible_name": tangible.tangible_name,
                "quantity": entry.quantity,
                "captured_rate": Decimal(tangible.final_cost or 0),
                "override_rate": entry.override_rate,
                "uom": entry.uom or tangible.uom,
                "currency": entry.currency or tangible.currency,
                "remarks": entry.remarks,
            }
        )
    return normalized


def normalize_estimate(
    db: Session, afe: Afe, payload: EstimateIn
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Validate a whole estimate payload and return its three normalized groups."""

    well = afe.well
    if well.is_deleted:
        raise AfeValidationError(
            f"Well {well.well_code} is in deleted entries — restore it before editing this AFE"
        )
    well_scope = build_well_scope(well)
    return (
        normalize_services(db, payload, well_scope),
        normalize_consumables(db, payload, well_scope),
        normalize_tangibles(db, payload),
    )


def _domain_lines(
    services: list[dict[str, Any]],
    consumables: list[dict[str, Any]],
    tangibles: list[dict[str, Any]],
) -> tuple[list[engine.ServiceLine], list[engine.ConsumableLine], list[engine.TangibleLine]]:
    """Build engine inputs from the normalized payload groups."""

    service_lines = [
        engine.ServiceLine(
            service_id=row["service_id"],
            service_code=row["service_code"],
            service_name=row["service_name"],
            provider_type=row["provider_type"],
            charging_basis=row["charging_basis"],
            rates=row["rates"],
            charge_lines=tuple(
                engine.ChargeLine(category=category, quantity=quantity, unit=unit)
                for category, quantity, unit in row["charge_lines"]
            ),
            section_rates=tuple(
                engine.SectionRate(section_id=section_id, phase_id=phase_id, amount=amount)
                for section_id, phase_id, amount in row["section_rates"]
            ),
            per_service_amount=row["per_service_amount"],
            section_id=row["section_id"],
            phase_id=row["phase_id"],
            effective_date=row["effective_date"],
            remarks=row["remarks"],
        )
        for row in services
    ]
    consumable_lines = [
        engine.ConsumableLine(
            item_id=row["item_id"],
            item_code=row["item_code"],
            item_name=row["item_name"],
            item_kind=row["item_kind"],
            quantity=row["quantity"],
            captured_rate=row["captured_rate"],
            override_rate=row["override_rate"],
            uom=row["uom"],
            currency=row["currency"],
            section_id=row["section_id"],
            phase_id=row["phase_id"],
        )
        for row in consumables
    ]
    tangible_lines = [
        engine.TangibleLine(
            tangible_id=row["tangible_id"],
            tangible_code=row["tangible_code"],
            tangible_name=row["tangible_name"],
            quantity=row["quantity"],
            captured_rate=row["captured_rate"],
            override_rate=row["override_rate"],
            uom=row["uom"],
            currency=row["currency"],
        )
        for row in tangibles
    ]
    return service_lines, consumable_lines, tangible_lines


def preview_estimate(db: Session, afe: Afe, payload: EstimateIn) -> dict[str, Any]:
    """Price an unsaved estimate with the same engine the save uses.

    Nothing is written: the cost estimation tab calls this (debounced) so the
    user sees live totals while typing, while the money rules stay in one
    framework-free place.
    """

    services, consumables, tangibles = normalize_estimate(db, afe, payload)
    well_scope = build_well_scope(afe.well)
    service_lines, consumable_lines, tangible_lines = _domain_lines(services, consumables, tangibles)
    estimate = engine.compile_afe_estimate(well_scope, service_lines, consumable_lines, tangible_lines)
    return {
        "services": [_line_estimate_out(line).model_dump() for line in estimate.services.lines],
        "consumables": [_line_estimate_out(line).model_dump() for line in estimate.consumables.lines],
        "tangibles": [_line_estimate_out(line).model_dump() for line in estimate.tangibles.lines],
        "summary": [
            {"group": group.group, "amount": group.amount, "line_count": group.line_count}
            for group in estimate.groups
        ],
        "by_section": [
            {
                "section_id": row.section_id,
                "section_label": row.section_label,
                "planned_days": row.planned_days,
                "amount": row.amount,
            }
            for row in estimate.by_section
        ],
        "grand_total": estimate.total,
        "warnings": list(estimate.warnings),
    }


def save_estimate(db: Session, afe: Afe, payload: EstimateIn, user: User) -> AfeEstimateOut:
    """Validate and replace the whole estimate of one AFE, then re-price it."""

    ensure_draft(afe)
    services, consumables, tangibles = normalize_estimate(db, afe, payload)

    service_rows = [
        AfeServiceLine(
            service_id=row["service_id"],
            charging_basis=row["charging_basis"],
            section_id=row["section_id"],
            phase_id=row["phase_id"],
            per_service_amount=row["per_service_amount"],
            effective_date=row["effective_date"],
            remarks=row["remarks"],
            sort_order=index,
            created_by=user.id,
            updated_by=user.id,
            rates=[
                AfeServiceRate(category=category, unit_rate=rate, created_by=user.id, updated_by=user.id)
                for category, rate in row["rates"].items()
                if rate != 0
            ],
            charge_lines=[
                AfeServiceChargeLine(
                    category=category,
                    quantity=quantity,
                    quantity_unit=unit,
                    sort_order=position,
                    created_by=user.id,
                    updated_by=user.id,
                )
                for position, (category, quantity, unit) in enumerate(row["charge_lines"])
            ],
            section_rates=[
                AfeServiceSectionRate(
                    section_id=section_id,
                    phase_id=phase_id,
                    amount=amount,
                    created_by=user.id,
                    updated_by=user.id,
                )
                for section_id, phase_id, amount in row["section_rates"]
            ],
        )
        for index, row in enumerate(services)
    ]
    consumable_rows = [
        AfeConsumableLine(
            item_kind=row["item_kind"],
            item_id=row["item_id"],
            item_code=row["item_code"],
            item_name=row["item_name"],
            quantity=row["quantity"],
            captured_rate=row["captured_rate"],
            override_rate=row["override_rate"],
            uom=row["uom"],
            currency=row["currency"],
            section_id=row["section_id"],
            phase_id=row["phase_id"],
            remarks=row["remarks"],
            sort_order=index,
            created_by=user.id,
            updated_by=user.id,
        )
        for index, row in enumerate(consumables)
    ]
    tangible_rows = [
        AfeTangibleLine(
            tangible_id=row["tangible_id"],
            quantity=row["quantity"],
            captured_rate=row["captured_rate"],
            override_rate=row["override_rate"],
            uom=row["uom"],
            currency=row["currency"],
            remarks=row["remarks"],
            sort_order=index,
            created_by=user.id,
            updated_by=user.id,
        )
        for index, row in enumerate(tangibles)
    ]

    _clear_lines(afe)
    afe.service_lines.extend(service_rows)
    afe.consumable_lines.extend(consumable_rows)
    afe.tangible_lines.extend(tangible_rows)
    afe.updated_by = user.id
    db.commit()
    db.refresh(afe)
    db.expire(afe, ["service_lines", "consumable_lines", "tangible_lines"])
    return build_estimate_out(afe)

# ---------------------------------------------------------------------------
# Status transitions (the only place the AFE status changes)
# ---------------------------------------------------------------------------


def change_status(
    db: Session, afe: Afe, action: str, remarks: str | None, user: User
) -> tuple[Afe, str]:
    """Move an AFE between draft / submitted / approved, with remarks."""

    note = (remarks or "").strip()
    if not note:
        raise AfeValidationError("Remarks are required for a status change")

    if action == "submit":
        if afe.status != engine.STATUS_DRAFT:
            raise AfeValidationError(f"AFE {afe.afe_code} is already {afe.status}")
        if not (afe.service_lines or afe.consumable_lines or afe.tangible_lines):
            raise AfeValidationError("Add at least one service, consumable or tangible before submitting")
        afe.status = engine.STATUS_SUBMITTED
        afe.submitted_at = datetime.now(UTC)
        detail = f"Submitted AFE {afe.afe_code}"
    elif action == "approve":
        if afe.status != engine.STATUS_SUBMITTED:
            raise AfeValidationError("Only a submitted AFE can be approved")
        afe.status = engine.STATUS_APPROVED
        afe.approved_at = datetime.now(UTC)
        detail = f"Approved AFE {afe.afe_code}"
    elif action == "reopen":
        if afe.status == engine.STATUS_DRAFT:
            raise AfeValidationError(f"AFE {afe.afe_code} is already a draft")
        previous = afe.status
        afe.status = engine.STATUS_DRAFT
        afe.approved_at = None
        detail = f"Reopened AFE {afe.afe_code} from {previous} back to draft"
    else:  # pragma: no cover - guarded by the Literal schema
        raise AfeValidationError(f"Unknown status action '{action}'")

    afe.status_remarks = note
    afe.updated_by = user.id
    db.commit()
    db.refresh(afe)
    return afe, f"{detail} — remarks: {note}"


# ---------------------------------------------------------------------------
# Export rows
# ---------------------------------------------------------------------------

EXPORT_HEADERS = [
    "afe_code",
    "afe_name",
    "afe_type",
    "rig",
    "well",
    "status",
    "cost_group",
    "code",
    "name",
    "charging_basis",
    "section",
    "phase",
    "charge_category",
    "quantity",
    "unit",
    "rate",
    "amount",
    "description",
]


def export_rows(db: Session, afes: list[Afe]) -> list[list[Any]]:
    """Flatten every priced component of every AFE into export rows."""

    rows: list[list[Any]] = []
    for afe in afes:
        estimate = compile_estimate(afe)
        rig = afe.rig
        well = afe.well
        header = [
            afe.afe_code,
            afe.afe_name,
            afe.afe_type,
            f"{rig.rig_code} - {rig.rig_name}" if rig else "",
            f"{well.well_code} - {well.well_name}" if well else "",
            afe.status,
        ]
        for group in estimate.groups:
            for line in group.lines:
                if not line.components:
                    rows.append([*header, group.group, line.code, line.name, line.basis or "", "", "", "", "", "", "", "0.00", "no charge configured"])
                    continue
                for component in line.components:
                    rows.append(
                        [
                            *header,
                            group.group,
                            line.code,
                            line.name,
                            line.basis or "",
                            component.section_label or "",
                            component.phase_label or "",
                            component.category,
                            str(component.quantity) if component.quantity is not None else "",
                            component.unit or "",
                            str(component.rate) if component.rate is not None else "",
                            str(component.amount),
                            component.description,
                        ]
                    )
    return rows
