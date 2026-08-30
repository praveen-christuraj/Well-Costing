"""Daily Costs API routes.

The daily page is **completely well scoped**: the user picks the Rig, then the
corresponding Well and then the date, and everything afterwards — the services,
the consumables, the tangibles, the imports, the exports, the print sheet and
the deleted entries — belongs to that rig + well + date.

Tabs served here
----------------
* **Daily Costs** — services (priced from the AFE rate card per charging basis
  and charge category, scoped to section / phase / well sub activity) and
  consumables (mud chemicals, fuel, cement additives, drill bits), saved as
  draft and then submitted.
* **Tangibles** — the block of tangibles entered at the end of the well, always
  picked from Master Data with an optional override unit rate.
* **Deleted Entries** — soft-deleted days, restorable or permanently removable.

Every action is audit-logged (module *Daily Costs*) and the common template is
in place: Import (XLSX/CSV), XLSX/CSV export, print-ready rows, edit, soft
delete. Money is never decided here — the routes resolve *which* rate applies
and :mod:`app.domain.daily_costing` does the pricing.

Path ordering note: static paths (``/context``, ``/rate-card``, ``/preview``,
``/entries/deleted``, ``/entries/export``, ``/entries/import`` …) are declared
before ``/entries/{record_id}`` so FastAPI matches them first.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportArgumentType=false, reportOptionalMemberAccess=false, reportUnknownParameterType=false, reportMissingTypeArgument=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false, reportOptionalIterable=false

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db
from app.domain.daily_costing import (
    CEMENT_ADDITIVE,
    DRILL_BIT,
    FUEL,
    MUD_CHEMICAL,
    STATUS_SUBMITTED,
    normalize_consumable_category,
)
from app.models.afe import Afe
from app.models.catalogue import DrillBit, MudChemical, Service, Tangible
from app.models.daily_cost import DailyCostEntry
from app.models.master_data import HoleSection, Phase
from app.models.rig_well import Rig, Well
from app.models.user import User
from app.models.well_sub_activity import WellSubActivity
from app.schemas.daily_cost import (
    DailyCostContextOut,
    DailyCostDayOut,
    DailyCostEntryIn,
    DailyCostEntryOut,
    DailyCostEntryUpdate,
    DailyCostPreviewIn,
    DailyCostSaveIn,
    DailyStatusIn,
    RateCardServiceOut,
)
from app.schemas.master_data import BulkImportResponse
from app.services import cost_reporting
from app.services import daily_cost as service
from app.services.afe_estimation import load_afe, load_afes
from app.services.audit import log_audit
from app.services.daily_cost import DailyCostValidationError
from app.services.import_helpers import (
    parse_date_flexible,
    parse_decimal,
    read_tabular_file,
    row_get,
    spreadsheet_response,
    template_xlsx_response,
)
from app.services.well_configuration import build_configuration_out

router = APIRouter(prefix="/daily-cost", tags=["daily-cost"])

MODULE = "Daily Costs"

COST_GROUPS = ("Service", "Consumable", "Tangible")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_entry(db: Session, record_id: int) -> DailyCostEntry:
    entry = db.get(DailyCostEntry, record_id)
    if not entry or entry.is_deleted:
        raise HTTPException(status_code=404, detail="Daily cost entry not found")
    return entry


def _get_well(db: Session, well_id: int) -> Well:
    well = db.get(Well, well_id)
    if not well or well.is_deleted:
        raise HTTPException(status_code=404, detail="Well not found or deleted")
    return well


def _get_afe(db: Session, afe_id: int | None, well: Well) -> Afe | None:
    if afe_id is None:
        return None
    afe = load_afe(db, afe_id, with_estimate_lines=True)
    if not afe or afe.is_deleted:
        raise HTTPException(status_code=404, detail="AFE not found")
    if afe.well_id != well.id:
        raise HTTPException(status_code=400, detail="The selected AFE belongs to another well")
    return afe


def pick_default_afe(afes: list[Afe]) -> Afe | None:
    """Prefer the newest submitted/approved AFE, else the newest one."""

    if not afes:
        return None
    for afe in reversed(afes):
        if afe.status in {"submitted", "approved"}:
            return afe
    return afes[-1]


def _find_entry(db: Session, well_id: int, cost_date: date) -> DailyCostEntry | None:
    return db.scalar(
        select(DailyCostEntry).where(
            DailyCostEntry.well_id == well_id,
            DailyCostEntry.cost_date == cost_date,
            DailyCostEntry.is_deleted == False,
        )
    )


def _sub_activity_rows(db: Session, well: Well) -> list[dict[str, Any]]:
    records = db.scalars(
        select(WellSubActivity)
        .where(WellSubActivity.well_id == well.id, WellSubActivity.is_deleted == False)
        .order_by(WellSubActivity.sub_activity_code)
    ).all()
    return [
        {
            "id": record.id,
            "sub_activity_code": record.sub_activity_code,
            "sub_activity_name": record.sub_activity_name,
            "activity_id": record.activity_id,
            "activity_code": record.activity.activity_code if record.activity else None,
            "activity_name": record.activity.activity_name if record.activity else None,
            "responsible_party": record.responsible_party,
            "display_name": f"{record.sub_activity_code} - {record.sub_activity_name}",
        }
        for record in records
    ]


# ---------------------------------------------------------------------------
# Context / rate card
# ---------------------------------------------------------------------------


@router.get("/context", response_model=DailyCostContextOut)
def get_context(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    well_id: int,
    afe_id: int | None = None,
) -> DailyCostContextOut:
    """Everything the daily page needs for one well: configuration, AFEs, sub
    activities and the AFE rate card the service picker prices from."""

    well = _get_well(db, well_id)
    afes = load_afes(db, well_id=well.id, with_estimate_lines=True)
    afe = _get_afe(db, afe_id, well) if afe_id is not None else pick_default_afe(afes)
    card = service.build_rate_card(db, afe)
    warnings: list[str] = []
    if not afes:
        warnings.append(
            "This well has no AFE yet — create one in AFE Management so the service rates are "
            "captured automatically. Until then enter override unit rates."
        )
    elif afe is None:
        warnings.append("No AFE selected — service rates must be entered manually.")
    if not well.sections:
        warnings.append(
            "This well has no configuration yet — configure its sections and phases in "
            "Rig & Well Management to scope the daily costs."
        )
    rig = well.rig
    return DailyCostContextOut(
        well_id=well.id,
        well_code=well.well_code or "",
        well_name=well.well_name or "",
        rig_id=well.rig_id,
        rig_code=rig.rig_code if rig else None,
        rig_name=rig.rig_name if rig else None,
        depth_unit=well.depth_unit or "m",
        well_configuration=build_configuration_out(well),
        afes=[
            {
                "id": item.id,
                "afe_code": item.afe_code,
                "afe_name": item.afe_name,
                "afe_type": item.afe_type,
                "status": item.status,
                "display_name": f"{item.afe_code} - {item.afe_name} ({item.afe_type}, {item.status})",
            }
            for item in afes
        ],
        sub_activities=_sub_activity_rows(db, well),
        rate_card=service.rate_card_out(card),
        afe_id=afe.id if afe else None,
        fuel_rate=service.fuel_rate_from_afe(db, afe),
        afe_estimated_total=sum(service.afe_group_totals(db, afe).values(), Decimal("0"))
        if afe is not None
        else Decimal("0"),
        warnings=warnings,
    )


@router.get("/rate-card", response_model=list[RateCardServiceOut])
def get_rate_card(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    afe_id: int,
) -> list[RateCardServiceOut]:
    """The unit rates one AFE configured per service, per charge category."""

    afe = db.get(Afe, afe_id)
    if not afe or afe.is_deleted:
        raise HTTPException(status_code=404, detail="AFE not found")
    return service.rate_card_out(service.build_rate_card(db, afe))


@router.post("/preview")
def preview_day(
    payload: DailyCostPreviewIn,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Price unsaved rows.

    The page calls this (debounced) so the totals on screen come from the same
    engine that saves them. Nothing is written and nothing is audited.
    """

    well = _get_well(db, payload.well_id)
    try:
        afe = _get_afe(db, payload.afe_id, well)
        return service.preview_day(db, well, afe, payload)
    except DailyCostValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


@router.get("/entries", response_model=list[DailyCostEntryOut])
def list_entries(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    well_id: int | None = None,
    rig_id: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    status: str | None = None,
    search: str | None = None,
) -> list[DailyCostEntryOut]:
    """The day sheets matching the page's context (rig / well / date range)."""

    stmt = select(DailyCostEntry).where(DailyCostEntry.is_deleted == False)
    if well_id is not None:
        stmt = stmt.where(DailyCostEntry.well_id == well_id)
    if rig_id is not None:
        stmt = stmt.where(DailyCostEntry.rig_id == rig_id)
    if from_date is not None:
        stmt = stmt.where(DailyCostEntry.cost_date >= from_date)
    if to_date is not None:
        stmt = stmt.where(DailyCostEntry.cost_date <= to_date)
    if status:
        stmt = stmt.where(DailyCostEntry.status == status)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            or_(
                DailyCostEntry.daily_cost_code.ilike(like),
                DailyCostEntry.remarks.ilike(like),
            )
        )
    records = db.scalars(stmt.order_by(DailyCostEntry.cost_date.desc(), DailyCostEntry.id.desc())).all()
    return [service.build_entry_out(entry) for entry in records]


@router.get("/entries/deleted", response_model=list[DailyCostEntryOut])
def list_deleted_entries(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    well_id: int | None = None,
) -> list[DailyCostEntryOut]:
    """Soft-deleted days (the Deleted Entries tab), optionally for one well."""

    stmt = select(DailyCostEntry).where(DailyCostEntry.is_deleted == True)
    if well_id is not None:
        stmt = stmt.where(DailyCostEntry.well_id == well_id)
    records = db.scalars(stmt.order_by(DailyCostEntry.deleted_at.desc())).all()
    return [service.build_entry_out(entry) for entry in records]


@router.get("/entries/for-date", response_model=DailyCostDayOut | None)
def get_entry_for_date(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    well_id: int,
    cost_date: date,
) -> DailyCostDayOut | None:
    """The day sheet for one well + date, or ``null`` when none exists yet."""

    _get_well(db, well_id)
    entry = _find_entry(db, well_id, cost_date)
    return service.build_day_out(entry) if entry else None


# ---------------------------------------------------------------------------
# Import / export
# ---------------------------------------------------------------------------


@router.get("/entries/import-template")
def download_import_template(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    """A ready-to-fill template covering services, consumables and tangibles."""

    well_codes = [str(code) for code in db.scalars(
        select(Well.well_code).where(Well.is_deleted == False).order_by(Well.well_code)
    ).all()]
    rig_codes = [str(code) for code in db.scalars(
        select(Rig.rig_code).where(Rig.is_deleted == False).order_by(Rig.rig_code)
    ).all()]
    section_codes = [str(code) for code in db.scalars(
        select(HoleSection.section_code).where(HoleSection.is_deleted == False).order_by(HoleSection.section_code)
    ).all()]
    phase_codes = [str(code) for code in db.scalars(
        select(Phase.phase_code).where(Phase.is_deleted == False).order_by(Phase.phase_code)
    ).all()]
    charge_categories = [
        "Mobilization", "Demobilization", "Operation", "Standby",
        "Personnel-Operation", "Personnel-Standby", "Fixed Charge", "Others",
    ]
    consumable_categories = ["Mud Chemicals", "Fuel", "Cement Additives", "Drill Bits"]
    return template_xlsx_response(
        "daily_costs_template",
        [
            "cost_date", "rig_code", "well_code", "afe_code", "cost_group", "category",
            "item_code", "section_code", "phase_code", "sub_activity_code",
            "quantity", "quantity_unit", "override_rate", "remarks",
        ],
        sample_rows=[
            ["2026-08-01", "RIG001", "WELL001", "AFE-2026-001", "Service", "Operation",
             "SVC-MWD", "SEC1", "DRL", "RIH-01", "12", "hours", "", "MWD while drilling"],
            ["2026-08-01", "RIG001", "WELL001", "AFE-2026-001", "Service", "Mobilization",
             "SVC-MWD", "SEC1", "", "", "1", "days", "", "One-time mobilization"],
            ["2026-08-01", "RIG001", "WELL001", "", "Consumable", "Mud Chemicals",
             "CHEM-001", "SEC1", "DRL", "", "25", "", "", "25 sacks consumed"],
            ["2026-08-01", "RIG001", "WELL001", "", "Consumable", "Fuel",
             "FUEL", "", "", "", "1200", "", "", "Diesel consumed"],
            ["2026-08-30", "RIG001", "WELL001", "", "Tangible", "Tangible",
             "TNG-CSG-9", "", "", "", "120", "", "", "Casing joints issued"],
        ],
        dropdowns={
            2: rig_codes,
            3: well_codes,
            5: [*COST_GROUPS],
            6: [*charge_categories, *consumable_categories, "Tangible"],
            8: section_codes,
            9: phase_codes,
            12: ["hours", "days"],
        },
        note=(
            "One row = one cost line of one day. cost_date accepts YYYY-MM-DD, DD/MM/YYYY, "
            "DD-MMM-YYYY or an Excel date. cost_group is Service, Consumable or Tangible. "
            "For a Service the category is the charge category (Mobilization, Demobilization, "
            "Operation, Standby, Personnel-Operation, Personnel-Standby, Fixed Charge, Others) "
            "and item_code is the service code from Master Data; the unit rate is taken from the "
            "AFE (override_rate replaces it). For a Consumable the category is Mud Chemicals, "
            "Fuel, Cement Additives or Drill Bits and item_code is the chemical/bit code "
            "(leave it blank for Fuel and Cement Additives). For a Tangible, item_code is the "
            "tangible code from Master Data. quantity is in hours (0-24) or days (0-1) for "
            "services and in the item's unit for consumables/tangibles; for Cement Additives put "
            "the total consumption cost in quantity. section_code / phase_code / "
            "sub_activity_code are optional and accept codes or names. Rows are merged into the "
            "day sheet of their well + date, which is created when it does not exist yet."
        ),
    )


def _resolve_rig(db: Session, ref: Any) -> Rig:
    text = str(ref or "").strip()
    if not text:
        raise DailyCostValidationError("rig_code is required")
    rig = db.scalar(select(Rig).where(Rig.rig_code == text, Rig.is_deleted == False))
    if rig:
        return rig
    rig = db.scalar(select(Rig).where(Rig.rig_code.ilike(text), Rig.is_deleted == False))
    if rig:
        return rig
    rig = db.scalar(select(Rig).where(Rig.rig_name.ilike(f"%{text}%"), Rig.is_deleted == False))
    if rig:
        return rig
    raise DailyCostValidationError(f"Rig '{text}' not found")


def _resolve_well(db: Session, ref: Any, rig: Rig) -> Well:
    text = str(ref or "").strip()
    if not text:
        raise DailyCostValidationError("well_code is required")
    stmt = select(Well).where(Well.rig_id == rig.id, Well.is_deleted == False)
    well = db.scalar(stmt.where(Well.well_code == text))
    if well:
        return well
    well = db.scalar(stmt.where(Well.well_code.ilike(text)))
    if well:
        return well
    well = db.scalar(stmt.where(Well.well_name.ilike(f"%{text}%")))
    if well:
        return well
    raise DailyCostValidationError(f"Well '{text}' not found under rig {rig.rig_code}")


def _resolve_section(db: Session, ref: Any) -> int | None:
    text = str(ref or "").strip()
    if not text:
        return None
    section = db.scalar(select(HoleSection).where(HoleSection.section_code == text, HoleSection.is_deleted == False))
    if section:
        return section.id
    section = db.scalar(select(HoleSection).where(HoleSection.section_code.ilike(text), HoleSection.is_deleted == False))
    if section:
        return section.id
    section = db.scalar(select(HoleSection).where(HoleSection.section_name.ilike(f"%{text}%"), HoleSection.is_deleted == False))
    if section:
        return section.id
    raise DailyCostValidationError(f"Hole section '{text}' not found in Master Data")


def _resolve_phase(db: Session, ref: Any) -> int | None:
    text = str(ref or "").strip()
    if not text:
        return None
    phase = db.scalar(select(Phase).where(Phase.phase_code == text, Phase.is_deleted == False))
    if phase:
        return phase.id
    phase = db.scalar(select(Phase).where(Phase.phase_code.ilike(text), Phase.is_deleted == False))
    if phase:
        return phase.id
    phase = db.scalar(select(Phase).where(Phase.phase_name.ilike(f"%{text}%"), Phase.is_deleted == False))
    if phase:
        return phase.id
    raise DailyCostValidationError(f"Phase '{text}' not found in Master Data")


def _resolve_sub_activity(db: Session, ref: Any, well: Well) -> int | None:
    text = str(ref or "").strip()
    if not text:
        return None
    stmt = select(WellSubActivity).where(
        WellSubActivity.well_id == well.id, WellSubActivity.is_deleted == False
    )
    record = db.scalar(stmt.where(WellSubActivity.sub_activity_code == text))
    if record:
        return record.id
    record = db.scalar(stmt.where(WellSubActivity.sub_activity_code.ilike(text)))
    if record:
        return record.id
    record = db.scalar(stmt.where(WellSubActivity.sub_activity_name.ilike(f"%{text}%")))
    if record:
        return record.id
    raise DailyCostValidationError(f"Well sub activity '{text}' not found for well {well.well_code}")


def _resolve_service(db: Session, ref: Any) -> Service:
    text = str(ref or "").strip()
    if not text:
        raise DailyCostValidationError("item_code (the service code) is required for a service line")
    record = db.scalar(select(Service).where(Service.service_code == text, Service.is_deleted == False))
    if record:
        return record
    record = db.scalar(select(Service).where(Service.service_code.ilike(text), Service.is_deleted == False))
    if record:
        return record
    record = db.scalar(select(Service).where(Service.service_name.ilike(f"%{text}%"), Service.is_deleted == False))
    if record:
        return record
    raise DailyCostValidationError(f"Service '{text}' not found in Master Data")


def _normalize_group(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"service", "services", "svc"}:
        return "Service"
    if text in {"consumable", "consumables", "cons"}:
        return "Consumable"
    if text in {"tangible", "tangibles", "tng"}:
        return "Tangible"
    raise DailyCostValidationError(
        f"cost_group '{value}' is not valid — use Service, Consumable or Tangible"
    )


@router.post("/entries/import", response_model=BulkImportResponse)
async def import_entries(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request = None,
) -> BulkImportResponse:
    """Bulk-import daily cost lines (services, consumables and tangibles).

    Rows are grouped by well + date: each group is appended to that day sheet
    (creating it when needed) and the whole day is re-priced by the engine, so
    an import produces exactly the same stored amounts as manual entry.
    """

    contents = await file.read()
    try:
        rows = read_tabular_file(contents, file.filename or "")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    imported = 0
    errors: list[str] = []
    # well_id -> cost_date -> {"services": [...], "consumables": [...], "tangibles": [...]}
    buckets: dict[tuple[int, date], dict[str, list[Any]]] = {}
    afe_by_well: dict[int, int | None] = {}

    for r_num, row in rows:
        try:
            cost_date = parse_date_flexible(row_get(row, "cost_date", "date", "day"))
            if cost_date is None:
                raise DailyCostValidationError("cost_date is required")
            rig = _resolve_rig(db, row_get(row, "rig_code", "rig", "rig_name"))
            well = _resolve_well(db, row_get(row, "well_code", "well", "well_name"), rig)
            group = _normalize_group(row_get(row, "cost_group", "group", "type") or "Service")
            category = str(row_get(row, "category", "charge_category", "consumable_category") or "").strip()
            item_code = row_get(row, "item_code", "code", "service_code", "item")
            section_id = _resolve_section(db, row_get(row, "section_code", "section", "hole_section"))
            phase_id = _resolve_phase(db, row_get(row, "phase_code", "phase"))
            sub_activity_id = _resolve_sub_activity(
                db, row_get(row, "sub_activity_code", "sub_activity", "well_sub_activity"), well
            )
            quantity_raw = row_get(row, "quantity", "qty", "usage", "hours", "days")
            quantity = parse_decimal(quantity_raw, field="quantity") or Decimal("0")
            unit = str(row_get(row, "quantity_unit", "unit") or "").strip().lower()
            if unit.startswith("h"):
                unit = "hours"
            elif unit.startswith("d"):
                unit = "days"
            elif group == "Service":
                unit = "hours"
            override_rate = parse_decimal(row_get(row, "override_rate", "override"), field="override rate")
            remarks = row_get(row, "remarks", "remark", "description")
        except (DailyCostValidationError, ValueError) as exc:
            errors.append(f"Row {r_num}: {exc}")
            continue

        if well.id not in afe_by_well:
            afe_ref = row_get(row, "afe_code", "afe")
            afe: Afe | None = None
            if afe_ref:
                afe = db.scalar(select(Afe).where(Afe.afe_code == str(afe_ref).strip(), Afe.well_id == well.id))
                if afe is None:
                    errors.append(f"Row {r_num}: AFE '{afe_ref}' not found for well {well.well_code}")
                    continue
            fallback = afe or pick_default_afe(
                load_afes(db, well_id=well.id, with_estimate_lines=True)
            )
            afe_by_well[well.id] = fallback.id if fallback else None

        bucket = buckets.setdefault(
            (well.id, cost_date), {"services": [], "consumables": [], "tangibles": []}
        )

        if group == "Service":
            try:
                service_record = _resolve_service(db, item_code)
            except DailyCostValidationError as exc:
                errors.append(f"Row {r_num}: {exc}")
                continue
            bucket["services"].append(
                {
                    "service_id": service_record.id,
                    "charge_category": category or "Operation",
                    "section_id": section_id,
                    "phase_id": phase_id,
                    "sub_activity_id": sub_activity_id,
                    "quantity": quantity,
                    "quantity_unit": unit or "hours",
                    "override_rate": override_rate,
                    "remarks": str(remarks) if remarks else None,
                }
            )
        elif group == "Consumable":
            try:
                consumable_category = _consumable_category(category)
            except DailyCostValidationError as exc:
                errors.append(f"Row {r_num}: {exc}")
                continue
            item_id, item_code_value, item_name = _resolve_consumable_item(
                db, consumable_category, item_code
            )
            if consumable_category == CEMENT_ADDITIVE:
                # The imported "quantity" column carries the total cost.
                bucket["consumables"].append(
                    {
                        "category": consumable_category,
                        "item_id": item_id,
                        "item_code": item_code_value,
                        "item_name": item_name,
                        "quantity": Decimal("0"),
                        "manual_amount": quantity,
                        "override_rate": override_rate,
                        "section_id": section_id,
                        "phase_id": phase_id,
                        "sub_activity_id": sub_activity_id,
                        "remarks": str(remarks) if remarks else None,
                    }
                )
            else:
                bucket["consumables"].append(
                    {
                        "category": consumable_category,
                        "item_id": item_id,
                        "item_code": item_code_value,
                        "item_name": item_name,
                        "quantity": quantity,
                        "override_rate": override_rate,
                        "section_id": section_id,
                        "phase_id": phase_id,
                        "sub_activity_id": sub_activity_id,
                        "remarks": str(remarks) if remarks else None,
                    }
                )
        else:
            try:
                tangible = _resolve_tangible(db, item_code)
            except DailyCostValidationError as exc:
                errors.append(f"Row {r_num}: {exc}")
                continue
            bucket["tangibles"].append(
                {
                    "tangible_id": tangible.id,
                    "quantity": quantity or Decimal("1"),
                    "override_rate": override_rate,
                    "remarks": str(remarks) if remarks else None,
                }
            )
        imported += 1

    saved_days = 0
    for (well_id, cost_date), bucket in buckets.items():
        well = db.get(Well, well_id)
        if well is None:
            continue
        try:
            entry = _find_entry(db, well_id, cost_date)
            if entry is None:
                entry = _create_entry(db, well, cost_date, afe_by_well.get(well_id), None, current_user)
            elif entry.status == STATUS_SUBMITTED:
                errors.append(
                    f"{entry.daily_cost_code}: the day is already submitted — reopen it before importing"
                )
                continue
            payload = DailyCostSaveIn(
                services=bucket["services"],
                consumables=bucket["consumables"],
                tangibles=bucket["tangibles"],
            )
            service.save_day(db, entry, payload, current_user)
            saved_days += 1
        except DailyCostValidationError as exc:
            errors.append(f"{well.well_code} {cost_date.isoformat()}: {exc}")
            db.rollback()

    log_audit(
        db, user=current_user, action="BULK_IMPORT", module=MODULE,
        details=(
            f"Imported {imported} daily cost line(s) into {saved_days} day sheet(s) "
            f"with {len(errors)} errors from {file.filename}"
        ),
        request=request,
    )
    return BulkImportResponse(
        imported_count=imported, error_count=len(errors), errors=errors[:30], success=not errors
    )


def _consumable_category(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        raise DailyCostValidationError(
            "category is required for a consumable line — Mud Chemicals, Fuel, Cement Additives or Drill Bits"
        )
    try:
        return normalize_consumable_category(text)
    except ValueError as exc:
        raise DailyCostValidationError(str(exc)) from exc


def _resolve_consumable_item(
    db: Session, category: str, ref: Any
) -> tuple[int | None, str | None, str | None]:
    """Resolve a consumable item; fuel and cement additives carry no item."""

    text = str(ref or "").strip()
    if category == FUEL:
        return (None, text or service.FUEL_CODE, text or service.FUEL_NAME)
    if category == CEMENT_ADDITIVE:
        return (None, text or service.CEMENT_CODE, text or service.CEMENT_NAME)
    if not text:
        raise DailyCostValidationError(f"item_code is required for {category}")
    if category == MUD_CHEMICAL:
        record = db.scalar(select(MudChemical).where(MudChemical.chemical_code == text, MudChemical.is_deleted == False))
        if record is None:
            record = db.scalar(select(MudChemical).where(MudChemical.chemical_code.ilike(text), MudChemical.is_deleted == False))
        if record is None:
            record = db.scalar(select(MudChemical).where(MudChemical.chemical_name.ilike(f"%{text}%"), MudChemical.is_deleted == False))
        if record is None:
            raise DailyCostValidationError(f"Mud chemical '{text}' not found in Master Data")
        return (record.id, record.chemical_code, record.chemical_name)
    if category != DRILL_BIT:  # pragma: no cover - guarded by the caller
        raise DailyCostValidationError(f"Unsupported consumable category '{category}'")
    record_bit = db.scalar(select(DrillBit).where(DrillBit.bit_code == text, DrillBit.is_deleted == False))
    if record_bit is None:
        record_bit = db.scalar(select(DrillBit).where(DrillBit.bit_code.ilike(text), DrillBit.is_deleted == False))
    if record_bit is None:
        record_bit = db.scalar(select(DrillBit).where(DrillBit.bit_name.ilike(f"%{text}%"), DrillBit.is_deleted == False))
    if record_bit is None:
        raise DailyCostValidationError(f"Drill bit '{text}' not found in Master Data")
    return (record_bit.id, record_bit.bit_code, record_bit.bit_name)


def _resolve_tangible(db: Session, ref: Any) -> Tangible:
    text = str(ref or "").strip()
    if not text:
        raise DailyCostValidationError("item_code (the tangible code) is required for a tangible line")
    record = db.scalar(select(Tangible).where(Tangible.tangible_code == text, Tangible.is_deleted == False))
    if record:
        return record
    record = db.scalar(select(Tangible).where(Tangible.tangible_code.ilike(text), Tangible.is_deleted == False))
    if record:
        return record
    record = db.scalar(select(Tangible).where(Tangible.tangible_name.ilike(f"%{text}%"), Tangible.is_deleted == False))
    if record:
        return record
    raise DailyCostValidationError(f"Tangible '{text}' not found in Master Data")


@router.get("/entries/export")
def export_entries(
    format: str = Query("xlsx", pattern="^(xlsx|csv)$"),
    well_id: int | None = None,
    rig_id: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    include_deleted: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request = None,
) -> Response:
    """The daily costs report: every line of every matching day."""

    entries = cost_reporting.list_entries(
        db,
        well_id=well_id,
        rig_id=rig_id,
        from_date=from_date,
        to_date=to_date,
        deleted=include_deleted,
    )
    rows = service.export_rows(db, entries)
    log_audit(
        db, user=current_user, action="EXPORT", module=MODULE,
        details=f"Exported {len(rows)} daily cost rows for {len(entries)} day(s) as {format}",
        request=request,
    )
    return spreadsheet_response(rows, service.EXPORT_HEADERS, "daily_costs", format)


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def _create_entry(
    db: Session,
    well: Well,
    cost_date: date,
    afe_id: int | None,
    remarks: str | None,
    user: User,
) -> DailyCostEntry:
    """Create (or revive) the day sheet of one well + date."""

    code = service.entry_code(well.well_code, cost_date)
    existing = db.scalar(
        select(DailyCostEntry).where(
            DailyCostEntry.well_id == well.id, DailyCostEntry.cost_date == cost_date
        )
    )
    if existing and existing.is_deleted:
        existing.is_deleted = False
        existing.deleted_at = None
        existing.status = "draft"
        existing.submitted_at = None
        existing.afe_id = afe_id
        existing.remarks = remarks
        existing.updated_by = user.id
        db.commit()
        db.refresh(existing)
        log_audit(
            db, user=user, action="RESTORE", module=MODULE,
            entity_id=existing.id, entity_code=code,
            details=f"Restored deleted daily cost {code} on create",
        )
        return existing
    if existing:
        return existing

    clash = db.scalar(select(DailyCostEntry).where(DailyCostEntry.daily_cost_code == code))
    if clash:
        # A renamed well could collide on the generated code; keep it unique.
        code = f"{code}-{well.id}"
    entry = DailyCostEntry(
        daily_cost_code=code,
        rig_id=well.rig_id,
        well_id=well.id,
        cost_date=cost_date,
        afe_id=afe_id,
        remarks=remarks,
        status="draft",
        reconciliation_status="pending",
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.post("/entries", response_model=DailyCostDayOut)
def create_entry(
    payload: DailyCostEntryIn,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> DailyCostDayOut:
    """Create the (empty) day sheet for one rig + well + date."""

    well = _get_well(db, payload.well_id)
    afe = _get_afe(db, payload.afe_id, well)
    if _find_entry(db, well.id, payload.cost_date):
        raise HTTPException(
            status_code=400,
            detail=f"A daily cost entry already exists for {well.well_code} on "
                   f"{payload.cost_date.isoformat()}",
        )
    entry = _create_entry(db, well, payload.cost_date, afe.id if afe else None, payload.remarks, current_user)
    log_audit(
        db, user=current_user, action="CREATE", module=MODULE,
        entity_id=entry.id, entity_code=entry.daily_cost_code,
        details=(
            f"Created daily cost {entry.daily_cost_code} for well {well.well_code} on "
            f"{entry.cost_date.isoformat()}"
        ),
        request=request,
    )
    return service.build_day_out(entry)


@router.get("/entries/{record_id}", response_model=DailyCostDayOut)
def get_entry(
    record_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DailyCostDayOut:
    return service.build_day_out(_get_entry(db, record_id))


@router.patch("/entries/{record_id}", response_model=DailyCostDayOut)
def update_entry_header(
    record_id: int,
    payload: DailyCostEntryUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> DailyCostDayOut:
    """Move a day to another date/AFE or change its remarks."""

    entry = _get_entry(db, record_id)
    if entry.status != "draft":
        raise HTTPException(
            status_code=400,
            detail=f"Daily cost {entry.daily_cost_code} is submitted — reopen it before editing.",
        )
    well = _get_well(db, entry.well_id)
    if payload.cost_date and payload.cost_date != entry.cost_date:
        if _find_entry(db, entry.well_id, payload.cost_date):
            raise HTTPException(
                status_code=400,
                detail=f"A daily cost entry already exists for {well.well_code} on "
                       f"{payload.cost_date.isoformat()}",
            )
        entry.cost_date = payload.cost_date
        entry.daily_cost_code = service.entry_code(well.well_code, payload.cost_date)
    if "afe_id" in payload.model_fields_set:
        afe = _get_afe(db, payload.afe_id, well)
        entry.afe_id = afe.id if afe else None
    if "remarks" in payload.model_fields_set:
        entry.remarks = payload.remarks
    entry.updated_by = current_user.id
    db.commit()
    db.refresh(entry)
    log_audit(
        db, user=current_user, action="UPDATE", module=MODULE,
        entity_id=entry.id, entity_code=entry.daily_cost_code,
        details=f"Updated daily cost header {entry.daily_cost_code}", request=request,
    )
    return service.build_day_out(entry)


@router.put("/entries/{record_id}", response_model=DailyCostDayOut)
def save_entry(
    record_id: int,
    payload: DailyCostSaveIn,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> DailyCostDayOut:
    """Save (replace) the whole day: services, consumables and tangibles."""

    entry = _get_entry(db, record_id)
    try:
        day = service.save_day(db, entry, payload, current_user)
    except DailyCostValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    log_audit(
        db, user=current_user, action="UPDATE", module=MODULE,
        entity_id=entry.id, entity_code=entry.daily_cost_code,
        details=(
            f"Saved daily cost {entry.daily_cost_code}: {len(payload.services)} service(s), "
            f"{len(payload.consumables)} consumable(s), {len(payload.tangibles)} tangible(s) "
            f"— total {day.grand_total}"
        ),
        request=request,
    )
    return day


@router.get("/entries/{record_id}/export")
def export_single_entry(
    record_id: int,
    format: str = Query("xlsx", pattern="^(xlsx|csv)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request = None,
) -> Response:
    """One day's cost report (the printable/exportable daily cost sheet)."""

    entry = _get_entry(db, record_id)
    rows = service.export_rows(db, [entry])
    log_audit(
        db, user=current_user, action="EXPORT", module=MODULE,
        entity_id=entry.id, entity_code=entry.daily_cost_code,
        details=f"Exported daily cost {entry.daily_cost_code} as {format}", request=request,
    )
    return spreadsheet_response(
        rows, service.EXPORT_HEADERS, f"daily_cost_{entry.daily_cost_code.replace('/', '-')}", format
    )


@router.post("/entries/{record_id}/status", response_model=DailyCostEntryOut)
def change_entry_status(
    record_id: int,
    payload: DailyStatusIn,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> DailyCostEntryOut:
    entry = _get_entry(db, record_id)
    try:
        entry, detail = service.change_status(db, entry, payload.action, payload.remarks, current_user)
    except DailyCostValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    log_audit(
        db, user=current_user, action="UPDATE", module=MODULE,
        entity_id=entry.id, entity_code=entry.daily_cost_code, details=detail, request=request,
    )
    return service.build_entry_out(entry)


@router.delete("/entries/{record_id}")
def soft_delete_entry(
    record_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> dict[str, Any]:
    entry = _get_entry(db, record_id)
    entry.is_deleted = True
    entry.deleted_at = datetime.now(UTC)
    entry.updated_by = current_user.id
    db.commit()
    log_audit(
        db, user=current_user, action="SOFT_DELETE", module=MODULE,
        entity_id=entry.id, entity_code=entry.daily_cost_code,
        details=f"Soft deleted daily cost {entry.daily_cost_code}", request=request,
    )
    return {"status": "success", "message": "Daily cost entry moved to deleted entries"}


@router.post("/entries/{record_id}/restore")
def restore_entry(
    record_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> dict[str, Any]:
    entry = db.get(DailyCostEntry, record_id)
    if not entry or not entry.is_deleted:
        raise HTTPException(status_code=404, detail="Deleted daily cost entry not found")
    clash = _find_entry(db, entry.well_id, entry.cost_date)
    if clash:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{clash.daily_cost_code} already covers this well and date — "
                "delete it first or move this entry to another date."
            ),
        )
    entry.is_deleted = False
    entry.deleted_at = None
    entry.updated_by = current_user.id
    db.commit()
    log_audit(
        db, user=current_user, action="RESTORE", module=MODULE,
        entity_id=entry.id, entity_code=entry.daily_cost_code,
        details=f"Restored daily cost {entry.daily_cost_code}", request=request,
    )
    return {"status": "success", "message": "Daily cost entry restored"}


@router.delete("/entries/{record_id}/permanent")
def permanent_delete_entry(
    record_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> dict[str, Any]:
    entry = db.get(DailyCostEntry, record_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Daily cost entry not found")
    code = entry.daily_cost_code
    db.delete(entry)
    db.commit()
    log_audit(
        db, user=current_user, action="PERMANENT_DELETE", module=MODULE,
        entity_id=record_id, entity_code=code,
        details=f"Permanently deleted daily cost {code} and its cost lines", request=request,
    )
    return {"status": "success", "message": "Daily cost entry permanently deleted"}
