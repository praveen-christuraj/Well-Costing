"""Drill Bits catalogue API (Consumables group).

Bit Type and Manufacturer are user-configurable dropdowns managed on the page
itself (values come from catalogue_configs). Final Cost is auto-calculated as
Unit Rate as per PO x Cost Uplift %. Rate changes append revisions to the
rate-revision history. Full common template: CRUD + soft delete + bulk import
+ export + rate-history export, all audited.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db
from app.models.catalogue import CatalogueConfig, DrillBit, DrillBitRate
from app.models.master_data import Currency
from app.models.user import User
from app.schemas.catalogue import DrillBitOut, MudChemicalRateOut
from app.schemas.master_data import BulkImportResponse
from app.services.audit import log_audit
from app.services.catalogue_rates import add_drill_bit_revision
from app.services.import_helpers import (
    final_cost,
    parse_date_flexible,
    parse_decimal,
    parse_uplift,
    read_tabular_file,
    row_get,
    spreadsheet_response,
    template_xlsx_response,
)

router = APIRouter(prefix="/catalogue/drill-bits", tags=["catalogue-drill-bits"])

MODULE_NAME = "Drill Bits"
CODE_PREFIX = "DB"

CONFIG_BIT_TYPE = "bit_type"
CONFIG_MANUFACTURER = "bit_manufacturer"


def _next_code(db: Session) -> str:
    highest = 0
    for code in db.scalars(select(DrillBit.bit_code)).all():
        digits = "".join(ch for ch in str(code) if ch.isdigit())
        if digits:
            highest = max(highest, int(digits))
    return f"{CODE_PREFIX}-{highest + 1:04d}"


def _config_values(db: Session, config_type: str) -> list[str]:
    rows = db.scalars(
        select(CatalogueConfig.value)
        .where(CatalogueConfig.config_type == config_type,
               CatalogueConfig.is_deleted == False,
               CatalogueConfig.is_active == True)
        .order_by(CatalogueConfig.sort_order, func.lower(CatalogueConfig.value))
    ).all()
    return [str(v) for v in rows]


def _resolve_config(db: Session, config_type: str, value: Any, *, create_if_missing: bool = False) -> str:
    """Resolve a dropdown value case-insensitively; optionally auto-create it."""

    val = str(value or "").strip()
    if not val:
        raise ValueError("Value is required")
    match = db.scalar(
        select(CatalogueConfig).where(
            CatalogueConfig.config_type == config_type,
            func.lower(CatalogueConfig.value) == val.lower(),
        )
    )
    if match:
        if match.is_deleted:
            match.is_deleted = False
            match.deleted_at = None
        return match.value
    if create_if_missing:
        max_order = db.scalar(select(func.max(CatalogueConfig.sort_order)).where(
            CatalogueConfig.config_type == config_type)) or 0
        created = CatalogueConfig(config_type=config_type, value=val, sort_order=max_order + 1)
        db.add(created)
        db.flush()
        return val
    known = ", ".join(_config_values(db, config_type)) or "none yet — add one via Manage"
    raise ValueError(f"'{val}' is not in the configured list ({known})")


def _resolve_currency(db: Session, ref: Any) -> str:
    val = str(ref or "").strip()
    if not val:
        raise ValueError("Currency is required")
    cur = db.scalar(
        select(Currency).where(
            or_(Currency.currency_code.ilike(val), Currency.currency_symbol.ilike(val),
                Currency.currency_name.ilike(f"%{val}%")),
            Currency.is_deleted == False,
        )
    )
    return cur.currency_code if cur else val


def _build_out(db: Session, bit: DrillBit) -> DrillBitOut:
    rates = db.scalars(
        select(DrillBitRate)
        .where(DrillBitRate.bit_id == bit.id, DrillBitRate.is_deleted == False)
        .order_by(DrillBitRate.revision_number.desc())
    ).all()
    latest = rates[0] if rates else None
    previous_final = Decimal("0")
    if latest and latest.revision_number > 1:
        prev = db.scalar(
            select(DrillBitRate).where(
                DrillBitRate.bit_id == bit.id,
                DrillBitRate.revision_number == latest.revision_number - 1,
            )
        )
        previous_final = prev.final_cost if prev else Decimal("0")
    rate_outs = [
        MudChemicalRateOut(
            id=r.id, bit_id=r.bit_id, item_kind="Drill Bit",
            item_code=bit.bit_code, item_name=bit.bit_name,
            unit_rate_po=r.unit_rate_po, cost_uplift=r.cost_uplift, final_cost=r.final_cost,
            currency=r.currency, effective_date=r.effective_date, revision_number=r.revision_number,
            po_number=r.po_number, remarks=r.remarks, is_deleted=r.is_deleted, created_at=r.created_at,
        )
        for r in rates
    ]
    return DrillBitOut(
        id=bit.id, bit_code=bit.bit_code, bit_name=bit.bit_name, bit_type=bit.bit_type,
        model_no=bit.model_no, size=bit.size, manufacturer=bit.manufacturer,
        po_number=bit.po_number, serial_number=bit.serial_number, currency=bit.currency,
        unit_rate_po=bit.unit_rate_po or Decimal("0"), cost_uplift=bit.cost_uplift or Decimal("100"),
        final_cost=bit.final_cost or Decimal("0"), previous_final_cost=previous_final,
        effective_date=bit.effective_date, description=bit.description, remarks=bit.remarks,
        is_deleted=bit.is_deleted, deleted_at=bit.deleted_at,
        created_at=bit.created_at, updated_at=bit.updated_at, rates=rate_outs,
    )


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


@router.get("")
def list_bits(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    search: str | None = None,
    bit_type: str | None = None,
) -> list[DrillBitOut]:
    stmt = select(DrillBit).where(DrillBit.is_deleted == False)
    if bit_type:
        stmt = stmt.where(DrillBit.bit_type == bit_type)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            or_(DrillBit.bit_name.ilike(like), DrillBit.bit_code.ilike(like),
                DrillBit.model_no.ilike(like), DrillBit.serial_number.ilike(like))
        )
    stmt = stmt.order_by(DrillBit.id.desc())
    return [_build_out(db, b) for b in db.scalars(stmt).all()]


@router.get("/dropdown-options")
def dropdown_options(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, list[str]]:
    return {
        "bit_types": _config_values(db, CONFIG_BIT_TYPE),
        "manufacturers": _config_values(db, CONFIG_MANUFACTURER),
    }


@router.get("/deleted")
def list_deleted_bits(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[DrillBitOut]:
    stmt = select(DrillBit).where(DrillBit.is_deleted == True).order_by(DrillBit.deleted_at.desc())
    return [_build_out(db, b) for b in db.scalars(stmt).all()]


@router.get("/rate-history")
def rate_history(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    bit_id: int | None = None,
) -> list[MudChemicalRateOut]:
    stmt = (
        select(DrillBitRate, DrillBit)
        .join(DrillBit, DrillBit.id == DrillBitRate.bit_id)
        .where(DrillBitRate.is_deleted == False, DrillBit.is_deleted == False)
        .order_by(DrillBitRate.effective_date.desc(), DrillBitRate.revision_number.desc())
    )
    if bit_id:
        stmt = stmt.where(DrillBitRate.bit_id == bit_id)
    out: list[MudChemicalRateOut] = []
    for rate, bit in db.execute(stmt).all():
        out.append(MudChemicalRateOut(
            id=rate.id, bit_id=rate.bit_id, item_kind="Drill Bit",
            item_code=bit.bit_code, item_name=bit.bit_name,
            unit_rate_po=rate.unit_rate_po, cost_uplift=rate.cost_uplift, final_cost=rate.final_cost,
            currency=rate.currency, effective_date=rate.effective_date,
            revision_number=rate.revision_number, po_number=rate.po_number,
            remarks=rate.remarks, created_at=rate.created_at,
        ))
    return out


@router.get("/rate-history/export")
def export_rate_history(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
    format: str = Query("xlsx", pattern="^(xlsx|csv)$"),
) -> Response:
    stmt = (
        select(DrillBitRate, DrillBit)
        .join(DrillBit, DrillBit.id == DrillBitRate.bit_id)
        .where(DrillBitRate.is_deleted == False)
        .order_by(DrillBit.bit_code, DrillBitRate.revision_number)
    )
    records = db.execute(stmt).all()
    log_audit(db, user=current_user, action="EXPORT", module=MODULE_NAME,
              details=f"Exported {len(records)} drill bit rate revisions as {format}", request=request)
    headers = ["bit_code", "bit_name", "revision_number", "effective_date",
               "unit_rate_po", "cost_uplift", "final_cost", "currency", "po_number", "remarks"]
    rows = [
        [bit.bit_code, bit.bit_name, rate.revision_number,
         rate.effective_date.isoformat() if rate.effective_date else "",
         str(rate.unit_rate_po), str(rate.cost_uplift), str(rate.final_cost),
         rate.currency or "", rate.po_number or "", rate.remarks or ""]
        for rate, bit in records
    ]
    return spreadsheet_response(rows, headers, "drill_bit_rate_history", format)


@router.get("/export")
def export_bits(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
    format: str = Query("xlsx", pattern="^(xlsx|csv)$"),
) -> Response:
    records = db.scalars(
        select(DrillBit).where(DrillBit.is_deleted == False).order_by(DrillBit.bit_code)
    ).all()
    log_audit(db, user=current_user, action="EXPORT", module=MODULE_NAME,
              details=f"Exported {len(records)} drill bits as {format}", request=request)
    headers = ["bit_code", "bit_name", "bit_type", "model_no", "size", "manufacturer",
               "po_number", "serial_number", "unit_rate_po", "cost_uplift", "final_cost",
               "currency", "effective_date", "description", "remarks"]
    rows = [
        [b.bit_code, b.bit_name, b.bit_type, b.model_no, b.size, b.manufacturer,
         b.po_number or "", b.serial_number or "", str(b.unit_rate_po), str(b.cost_uplift),
         str(b.final_cost), b.currency or "",
         b.effective_date.isoformat() if b.effective_date else "",
         b.description or "", b.remarks or ""]
        for b in records
    ]
    return spreadsheet_response(rows, headers, "drill_bits_export", format)


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def _parse_payload(db: Session, payload: dict[str, Any], *, create: bool) -> dict[str, Any]:
    name = str(payload.get("bit_name") or payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Bit Name is required")
    model_no = str(payload.get("model_no") or payload.get("model") or "").strip()
    if not model_no:
        raise HTTPException(status_code=400, detail="Model No is required")
    size = str(payload.get("size") or "").strip()
    if not size:
        raise HTTPException(status_code=400, detail="Size is required")

    bit_type = payload.get("bit_type")
    manufacturer = payload.get("manufacturer")
    if create and not bit_type:
        raise HTTPException(status_code=400, detail="Bit Type is required")
    if create and not manufacturer:
        raise HTTPException(status_code=400, detail="Manufacturer is required")
    try:
        bit_type_val = _resolve_config(db, CONFIG_BIT_TYPE, bit_type) if bit_type else None
        manufacturer_val = _resolve_config(db, CONFIG_MANUFACTURER, manufacturer) if manufacturer else None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    rate = parse_decimal(
        payload.get("unit_rate_po") if "unit_rate_po" in payload else payload.get("unit_rate"),
        field="Unit Rate as per PO", allow_blank=not create,
    )
    if create and (rate is None or rate < 0):
        raise HTTPException(status_code=400, detail="Unit Rate as per PO is required and must be >= 0")
    uplift = parse_uplift(payload.get("cost_uplift"), default=Decimal("100"))
    currency_raw = payload.get("currency")
    if create and (not currency_raw or str(currency_raw).strip() == ""):
        raise HTTPException(status_code=400, detail="Currency is required")
    currency = _resolve_currency(db, currency_raw) if currency_raw not in (None, "") else None
    eff = parse_date_flexible(payload.get("effective_date")) if payload.get("effective_date") not in (None, "") else date.today()
    if eff is None:
        eff = date.today()

    return {
        "name": name,
        "bit_type": bit_type_val,
        "model_no": model_no,
        "size": size,
        "manufacturer": manufacturer_val,
        "po_number": str(payload.get("po_number") or "").strip() or None,
        "serial_number": str(payload.get("serial_number") or payload.get("serial_no") or "").strip() or None,
        "unit_rate_po": rate if rate is not None else Decimal("0"),
        "cost_uplift": uplift,
        "final_cost": final_cost(rate if rate is not None else Decimal("0"), uplift),
        "currency": currency,
        "effective_date": eff,
        "description": payload.get("description") or None,
        "remarks": payload.get("remarks") or None,
    }


@router.post("")
def create_bit(
    payload: dict[str, Any],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> DrillBitOut:
    data = _parse_payload(db, payload, create=True)
    dup = db.scalar(
        select(DrillBit).where(
            func.lower(DrillBit.bit_name) == data["name"].lower(),
            func.lower(DrillBit.model_no) == data["model_no"].lower(),
            func.lower(DrillBit.size) == data["size"].lower(),
            DrillBit.is_deleted == False,
        )
    )
    if dup:
        raise HTTPException(status_code=400,
                            detail=f"Bit '{data['name']}' (model {data['model_no']}, size {data['size']}) already exists — code {dup.bit_code}")

    bit = DrillBit(
        bit_code=_next_code(db),
        bit_name=data["name"], bit_type=data["bit_type"], model_no=data["model_no"],
        size=data["size"], manufacturer=data["manufacturer"], po_number=data["po_number"],
        serial_number=data["serial_number"], currency=data["currency"],
        unit_rate_po=data["unit_rate_po"], cost_uplift=data["cost_uplift"],
        final_cost=data["final_cost"], effective_date=data["effective_date"],
        description=data["description"], remarks=data["remarks"],
        created_by=current_user.id, updated_by=current_user.id,
    )
    db.add(bit)
    db.flush()
    add_drill_bit_revision(
        db, bit, unit_rate_po=data["unit_rate_po"], cost_uplift=data["cost_uplift"],
        currency=data["currency"], effective_date=data["effective_date"],
        po_number=data["po_number"], remarks=data["remarks"], user=current_user,
    )
    db.commit()
    db.refresh(bit)
    log_audit(db, user=current_user, action="CREATE", module=MODULE_NAME, entity_id=bit.id,
              entity_code=bit.bit_code,
              details=f"Created drill bit {bit.bit_code} - {bit.bit_name} final cost {bit.final_cost} {bit.currency or ''}",
              request=request)
    return _build_out(db, bit)


@router.put("/{record_id}")
def update_bit(
    record_id: int,
    payload: dict[str, Any],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> DrillBitOut:
    bit = db.get(DrillBit, record_id)
    if not bit or bit.is_deleted:
        raise HTTPException(status_code=404, detail="Drill bit not found")

    new_name = str(payload.get("bit_name") or payload.get("name") or bit.bit_name).strip()
    new_model = str(payload.get("model_no") or payload.get("model") or bit.model_no).strip()
    new_size = str(payload.get("size") or bit.size).strip()
    if (new_name.lower() != bit.bit_name.lower() or new_model.lower() != bit.model_no.lower()
            or new_size.lower() != bit.size.lower()):
        clash = db.scalar(
            select(DrillBit).where(
                func.lower(DrillBit.bit_name) == new_name.lower(),
                func.lower(DrillBit.model_no) == new_model.lower(),
                func.lower(DrillBit.size) == new_size.lower(),
                DrillBit.id != record_id,
                DrillBit.is_deleted == False,
            )
        )
        if clash:
            raise HTTPException(status_code=400, detail="Another drill bit with the same name, model and size already exists")
    bit.bit_name = new_name
    bit.model_no = new_model
    bit.size = new_size

    if payload.get("bit_type") not in (None, ""):
        try:
            bit.bit_type = _resolve_config(db, CONFIG_BIT_TYPE, payload["bit_type"])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    if payload.get("manufacturer") not in (None, ""):
        try:
            bit.manufacturer = _resolve_config(db, CONFIG_MANUFACTURER, payload["manufacturer"])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    if "po_number" in payload:
        bit.po_number = str(payload.get("po_number") or "").strip() or None
    if "serial_number" in payload:
        bit.serial_number = str(payload.get("serial_number") or "").strip() or None
    if "description" in payload:
        bit.description = payload.get("description") or None
    if "remarks" in payload:
        bit.remarks = payload.get("remarks") or None

    revision_added = False
    has_rate = payload.get("unit_rate_po") not in (None, "") or payload.get("unit_rate") not in (None, "")
    if has_rate:
        rate = parse_decimal(
            payload.get("unit_rate_po") if "unit_rate_po" in payload else payload.get("unit_rate"),
            field="Unit Rate as per PO", allow_blank=False)
        if rate is None or rate < 0:
            raise HTTPException(status_code=400, detail="Unit Rate as per PO must be >= 0")
        uplift = parse_uplift(payload.get("cost_uplift"), default=bit.cost_uplift or Decimal("100"))
        currency = bit.currency
        if payload.get("currency") not in (None, ""):
            currency = _resolve_currency(db, payload["currency"])
        if not currency:
            raise HTTPException(status_code=400, detail="Currency is required")
        eff = parse_date_flexible(payload.get("effective_date")) if payload.get("effective_date") not in (None, "") else date.today()
        rev = add_drill_bit_revision(
            db, bit, unit_rate_po=rate, cost_uplift=uplift, currency=currency,
            effective_date=eff, po_number=bit.po_number,
            remarks=payload.get("remarks") or bit.remarks, user=current_user,
        )
        revision_added = rev is not None
    elif payload.get("cost_uplift") not in (None, ""):
        # Uplift-only change still changes final cost → revision.
        uplift = parse_uplift(payload.get("cost_uplift"), default=bit.cost_uplift or Decimal("100"))
        rev = add_drill_bit_revision(
            db, bit, unit_rate_po=bit.unit_rate_po, cost_uplift=uplift, currency=bit.currency,
            effective_date=date.today(), po_number=bit.po_number, remarks=bit.remarks, user=current_user,
        )
        revision_added = rev is not None
    if payload.get("currency") not in (None, "") and not has_rate:
        bit.currency = _resolve_currency(db, payload["currency"])

    bit.updated_by = current_user.id
    db.commit()
    db.refresh(bit)
    log_audit(db, user=current_user,
              action="RATE_REVISION" if revision_added else "UPDATE",
              module=MODULE_NAME, entity_id=bit.id, entity_code=bit.bit_code,
              details=(f"Rate revision for {bit.bit_code}: final cost {bit.final_cost} {bit.currency or ''}"
                       if revision_added else f"Updated drill bit {bit.bit_code}"),
              request=request)
    return _build_out(db, bit)


@router.delete("/{record_id}")
def soft_delete_bit(
    record_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> dict[str, str]:
    bit = db.get(DrillBit, record_id)
    if not bit or bit.is_deleted:
        raise HTTPException(status_code=404, detail="Drill bit not found")
    bit.is_deleted = True
    bit.deleted_at = datetime.now(UTC)
    db.commit()
    log_audit(db, user=current_user, action="SOFT_DELETE", module=MODULE_NAME, entity_id=bit.id,
              entity_code=bit.bit_code, details=f"Soft deleted drill bit {bit.bit_code}", request=request)
    return {"status": "success", "message": "Drill bit moved to deleted entries"}


@router.post("/{record_id}/restore")
def restore_bit(
    record_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> dict[str, str]:
    bit = db.get(DrillBit, record_id)
    if not bit or not bit.is_deleted:
        raise HTTPException(status_code=404, detail="Deleted drill bit not found")
    bit.is_deleted = False
    bit.deleted_at = None
    db.commit()
    log_audit(db, user=current_user, action="RESTORE", module=MODULE_NAME, entity_id=bit.id,
              entity_code=bit.bit_code, details=f"Restored drill bit {bit.bit_code}", request=request)
    return {"status": "success", "message": "Drill bit restored"}


@router.delete("/{record_id}/permanent")
def permanent_delete_bit(
    record_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> dict[str, str]:
    bit = db.get(DrillBit, record_id)
    if not bit:
        raise HTTPException(status_code=404, detail="Drill bit not found")
    code = bit.bit_code
    db.delete(bit)
    db.commit()
    log_audit(db, user=current_user, action="PERMANENT_DELETE", module=MODULE_NAME, entity_id=record_id,
              entity_code=code, details=f"Permanently deleted drill bit {code} and its rate history",
              request=request)
    return {"status": "success", "message": "Drill bit permanently deleted"}


# ---------------------------------------------------------------------------
# Bulk import
# ---------------------------------------------------------------------------

IMPORT_HEADERS = [
    "bit_name", "bit_type", "model_no", "size", "manufacturer", "po_number", "serial_number",
    "unit_rate_po", "cost_uplift", "currency", "effective_date", "description", "remarks",
]


@router.get("/import-template")
def download_template(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    """XLSX template — download, fill with data, upload the same file."""

    currencies = [str(code) for code in db.scalars(
        select(Currency.currency_code).where(Currency.is_deleted == False)
        .order_by(Currency.currency_code)
    ).all()]
    return template_xlsx_response(
        "drill_bits_template",
        IMPORT_HEADERS,
        sample_rows=[
            ["PDC Drill Bit", "PDC", "M-500", "12 1/4", "Schlumberger", "PO-2026-01", "SN-001",
             45000, 100, "USD", "2026-01-20", "Polycrystalline diamond compact", "First batch"],
        ],
        dropdowns={
            2: _config_values(db, CONFIG_BIT_TYPE),
            5: _config_values(db, CONFIG_MANUFACTURER),
            10: currencies,
        },
        note=("Bit codes are generated automatically on import; bit types and manufacturers that "
              "are not configured yet are created automatically. Re-importing an existing bit "
              "with a new rate appends a rate revision."),
    )


@router.post("/import", response_model=BulkImportResponse)
async def import_bits(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
    file: UploadFile = File(...),
) -> BulkImportResponse:
    filename = file.filename or ""
    try:
        rows = read_tabular_file(await file.read(), filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {exc}") from exc

    imported = 0
    errors: list[str] = []
    for r_num, row in rows:
        try:
            name = str(row_get(row, "bit_name", "name") or "").strip()
            if not name:
                raise ValueError("Bit Name is required")
            bit_type = str(row_get(row, "bit_type", "type") or "").strip()
            model_no = str(row_get(row, "model_no", "model") or "").strip()
            size = str(row_get(row, "size") or "").strip()
            manufacturer = str(row_get(row, "manufacturer", "make") or "").strip()
            if not (bit_type and model_no and size and manufacturer):
                raise ValueError("bit_type, model_no, size and manufacturer are required")
            bit_type_val = _resolve_config(db, CONFIG_BIT_TYPE, bit_type, create_if_missing=True)
            manufacturer_val = _resolve_config(db, CONFIG_MANUFACTURER, manufacturer, create_if_missing=True)

            rate = parse_decimal(row_get(row, "unit_rate_po", "unit_rate", "rate"),
                                 field="Unit Rate as per PO", allow_blank=False)
            if rate is None or rate < 0:
                raise ValueError("Unit Rate as per PO is required and must be >= 0")
            uplift = parse_uplift(row_get(row, "cost_uplift", "uplift"), default=Decimal("100"))
            currency = _resolve_currency(db, row_get(row, "currency", "curr"))
            eff = parse_date_flexible(row_get(row, "effective_date", "date")) or date.today()
            po_number = str(row_get(row, "po_number", "po") or "").strip() or None
            serial = str(row_get(row, "serial_number", "serial_no", "serial") or "").strip() or None
            desc = row_get(row, "description", "desc")
            remarks = row_get(row, "remarks", "remark")

            existing = db.scalar(
                select(DrillBit).where(
                    func.lower(DrillBit.bit_name) == name.lower(),
                    func.lower(DrillBit.model_no) == model_no.lower(),
                    func.lower(DrillBit.size) == size.lower(),
                )
            )
            if existing:
                if existing.is_deleted:
                    existing.is_deleted = False
                    existing.deleted_at = None
                existing.bit_type = bit_type_val
                existing.manufacturer = manufacturer_val
                existing.po_number = po_number or existing.po_number
                existing.serial_number = serial or existing.serial_number
                existing.description = str(desc) if desc else existing.description
                existing.remarks = str(remarks) if remarks else existing.remarks
                add_drill_bit_revision(
                    db, existing, unit_rate_po=rate, cost_uplift=uplift, currency=currency,
                    effective_date=eff, po_number=po_number,
                    remarks=str(remarks) if remarks else None, user=current_user,
                )
                existing.updated_by = current_user.id
            else:
                bit = DrillBit(
                    bit_code=_next_code(db),
                    bit_name=name, bit_type=bit_type_val, model_no=model_no, size=size,
                    manufacturer=manufacturer_val, po_number=po_number, serial_number=serial,
                    currency=currency, unit_rate_po=rate, cost_uplift=uplift,
                    final_cost=final_cost(rate, uplift), effective_date=eff,
                    description=str(desc) if desc else None,
                    remarks=str(remarks) if remarks else None,
                    created_by=current_user.id, updated_by=current_user.id,
                )
                db.add(bit)
                db.flush()
                add_drill_bit_revision(
                    db, bit, unit_rate_po=rate, cost_uplift=uplift, currency=currency,
                    effective_date=eff, po_number=po_number,
                    remarks=str(remarks) if remarks else None, user=current_user,
                )
            imported += 1
            db.flush()
        except Exception as exc:
            errors.append(f"Row {r_num}: {exc}")

    db.commit()
    log_audit(db, user=current_user, action="BULK_IMPORT", module=MODULE_NAME,
              details=f"Imported {imported} drill bits with {len(errors)} errors from {filename}",
              request=request)
    return BulkImportResponse(imported_count=imported, error_count=len(errors),
                              errors=errors[:30], success=not errors)
