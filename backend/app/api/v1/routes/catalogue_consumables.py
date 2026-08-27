"""Mud Chemicals catalogue API (Consumables group).

Items carry an auto-generated code and an append-only rate-revision history:
creating an item records revision #1 and subsequent rate changes append new
revisions (Previous Price auto-detected from the last revision). Exposes
list/create/update/soft-delete/restore/permanent-delete, bulk import, xlsx/csv
export and a rate-revision-history view with its own export — all audited.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db
from app.models.catalogue import MudChemical, MudChemicalRate
from app.models.master_data import Currency, UnitOfMeasurement
from app.models.user import User
from app.schemas.catalogue import MudChemicalOut, MudChemicalRateOut
from app.schemas.master_data import BulkImportResponse
from app.services.audit import log_audit
from app.services.catalogue_rates import add_mud_chemical_revision
from app.services.import_helpers import (
    parse_date_flexible,
    parse_decimal,
    read_tabular_file,
    row_get,
    spreadsheet_response,
)

router = APIRouter(prefix="/catalogue/mud-chemicals", tags=["catalogue-mud-chemicals"])

MODULE_NAME = "Mud Chemicals"
CODE_PREFIX = "MC"


def _next_code(db: Session) -> str:
    highest = 0
    for code in db.scalars(select(MudChemical.chemical_code)).all():
        digits = "".join(ch for ch in str(code) if ch.isdigit())
        if digits:
            highest = max(highest, int(digits))
    return f"{CODE_PREFIX}-{highest + 1:04d}"


def _resolve_uom(db: Session, ref: Any) -> str | None:
    if ref is None or str(ref).strip() == "":
        return None
    val = str(ref).strip()
    uom = db.scalar(
        select(UnitOfMeasurement).where(
            or_(UnitOfMeasurement.unit_code.ilike(val), UnitOfMeasurement.unit_name.ilike(val),
                UnitOfMeasurement.unit_symbol.ilike(val)),
            UnitOfMeasurement.is_deleted == False,
        )
    )
    return uom.unit_code if uom else val


def _resolve_currency(db: Session, ref: Any) -> str | None:
    if ref is None or str(ref).strip() == "":
        return None
    val = str(ref).strip()
    cur = db.scalar(
        select(Currency).where(
            or_(Currency.currency_code.ilike(val), Currency.currency_symbol.ilike(val),
                Currency.currency_name.ilike(f"%{val}%")),
            Currency.is_deleted == False,
        )
    )
    return cur.currency_code if cur else val


def _latest_rate(db: Session, chemical_id: int) -> MudChemicalRate | None:
    return db.scalar(
        select(MudChemicalRate)
        .where(MudChemicalRate.chemical_id == chemical_id, MudChemicalRate.is_deleted == False)
        .order_by(MudChemicalRate.revision_number.desc())
    )


def _build_out(db: Session, chem: MudChemical) -> MudChemicalOut:
    latest = _latest_rate(db, chem.id)
    rates = db.scalars(
        select(MudChemicalRate)
        .where(MudChemicalRate.chemical_id == chem.id, MudChemicalRate.is_deleted == False)
        .order_by(MudChemicalRate.revision_number.desc())
    ).all()
    rate_outs = [
        MudChemicalRateOut(
            id=r.id, chemical_id=r.chemical_id, item_kind="Mud Chemical",
            item_code=chem.chemical_code, item_name=chem.chemical_name,
            unit_rate=r.unit_rate, previous_rate=r.previous_rate, currency=r.currency,
            uom=r.uom, effective_date=r.effective_date, revision_number=r.revision_number,
            remarks=r.remarks, is_deleted=r.is_deleted, created_at=r.created_at,
        )
        for r in rates
    ]
    return MudChemicalOut(
        id=chem.id,
        chemical_code=chem.chemical_code,
        part_number=chem.part_number,
        chemical_name=chem.chemical_name,
        uom=chem.uom,
        currency=chem.currency,
        current_rate=chem.current_rate or Decimal("0"),
        previous_rate=(latest.previous_rate if latest else Decimal("0")),
        effective_date=chem.effective_date,
        description=chem.description,
        is_deleted=chem.is_deleted,
        deleted_at=chem.deleted_at,
        created_at=chem.created_at,
        updated_at=chem.updated_at,
        rates=rate_outs,
    )


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


@router.get("", response_model=list[MudChemicalOut])
def list_chemicals(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    search: str | None = None,
) -> list[MudChemicalOut]:
    stmt = select(MudChemical).where(MudChemical.is_deleted == False)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            or_(MudChemical.chemical_name.ilike(like), MudChemical.chemical_code.ilike(like),
                MudChemical.part_number.ilike(like))
        )
    stmt = stmt.order_by(MudChemical.id.desc())
    return [_build_out(db, c) for c in db.scalars(stmt).all()]


@router.get("/deleted", response_model=list[MudChemicalOut])
def list_deleted_chemicals(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[MudChemicalOut]:
    stmt = select(MudChemical).where(MudChemical.is_deleted == True).order_by(MudChemical.deleted_at.desc())
    return [_build_out(db, c) for c in db.scalars(stmt).all()]


@router.get("/rate-history", response_model=list[MudChemicalRateOut])
def rate_history(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    chemical_id: int | None = None,
) -> list[MudChemicalRateOut]:
    """Full rate-revision history across mud chemicals (latest first)."""

    stmt = (
        select(MudChemicalRate, MudChemical)
        .join(MudChemical, MudChemical.id == MudChemicalRate.chemical_id)
        .where(MudChemicalRate.is_deleted == False, MudChemical.is_deleted == False)
        .order_by(MudChemicalRate.effective_date.desc(), MudChemicalRate.revision_number.desc())
    )
    if chemical_id:
        stmt = stmt.where(MudChemicalRate.chemical_id == chemical_id)
    out: list[MudChemicalRateOut] = []
    for rate, chem in db.execute(stmt).all():
        out.append(MudChemicalRateOut(
            id=rate.id, chemical_id=rate.chemical_id, item_kind="Mud Chemical",
            item_code=chem.chemical_code, item_name=chem.chemical_name,
            unit_rate=rate.unit_rate, previous_rate=rate.previous_rate, currency=rate.currency,
            uom=rate.uom, effective_date=rate.effective_date, revision_number=rate.revision_number,
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
        select(MudChemicalRate, MudChemical)
        .join(MudChemical, MudChemical.id == MudChemicalRate.chemical_id)
        .where(MudChemicalRate.is_deleted == False)
        .order_by(MudChemical.chemical_code, MudChemicalRate.revision_number)
    )
    records = db.execute(stmt).all()
    log_audit(db, user=current_user, action="EXPORT", module=MODULE_NAME,
              details=f"Exported {len(records)} mud chemical rate revisions as {format}", request=request)
    headers = ["chemical_code", "chemical_name", "revision_number", "effective_date",
               "previous_rate", "unit_rate", "currency", "uom", "remarks"]
    rows = [
        [chem.chemical_code, chem.chemical_name, rate.revision_number,
         rate.effective_date.isoformat() if rate.effective_date else "",
         str(rate.previous_rate), str(rate.unit_rate), rate.currency or "",
         rate.uom or "", rate.remarks or ""]
        for rate, chem in records
    ]
    return spreadsheet_response(rows, headers, "mud_chemical_rate_history", format)


@router.get("/export")
def export_chemicals(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
    format: str = Query("xlsx", pattern="^(xlsx|csv)$"),
) -> Response:
    records = db.scalars(
        select(MudChemical).where(MudChemical.is_deleted == False).order_by(MudChemical.chemical_code)
    ).all()
    log_audit(db, user=current_user, action="EXPORT", module=MODULE_NAME,
              details=f"Exported {len(records)} mud chemicals as {format}", request=request)
    headers = ["chemical_code", "part_number", "chemical_name", "uom", "unit_rate",
               "currency", "effective_date", "description"]
    rows = [
        [c.chemical_code, c.part_number or "", c.chemical_name, c.uom or "",
         str(c.current_rate or ""), c.currency or "",
         c.effective_date.isoformat() if c.effective_date else "", c.description or ""]
        for c in records
    ]
    return spreadsheet_response(rows, headers, "mud_chemicals_export", format)


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def _parse_item_payload(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalise a mud chemical payload (raises HTTPException)."""

    name = str(payload.get("chemical_name") or payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Chemical Name is required")
    rate = parse_decimal(payload.get("unit_rate") if "unit_rate" in payload else payload.get("current_rate"),
                         field="Unit Rate", allow_blank=False)
    if rate is None or rate < 0:
        raise HTTPException(status_code=400, detail="Unit Rate is required and must not be negative")
    currency_raw = payload.get("currency")
    if not currency_raw or str(currency_raw).strip() == "":
        raise HTTPException(status_code=400, detail="Currency is required")
    eff_raw = payload.get("effective_date")
    effective_date = parse_date_flexible(eff_raw) if eff_raw not in (None, "") else date.today()
    if effective_date is None:
        effective_date = date.today()
    return {
        "name": name,
        "part_number": str(payload.get("part_number") or "").strip() or None,
        "uom": _resolve_uom(db, payload.get("uom")),
        "currency": _resolve_currency(db, currency_raw),
        "unit_rate": rate,
        "effective_date": effective_date,
        "description": payload.get("description") or None,
        "remarks": payload.get("remarks") or None,
    }


@router.post("", response_model=MudChemicalOut)
def create_chemical(
    payload: dict[str, Any],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> MudChemicalOut:
    data = _parse_item_payload(db, payload)
    dup = db.scalar(
        select(MudChemical).where(
            func.lower(MudChemical.chemical_name) == data["name"].lower(),
            MudChemical.is_deleted == False,
        )
    )
    if dup:
        raise HTTPException(status_code=400,
                            detail=f"Chemical '{data['name']}' already exists (code {dup.chemical_code})")

    chem = MudChemical(
        chemical_code=_next_code(db),
        part_number=data["part_number"],
        chemical_name=data["name"],
        uom=data["uom"],
        currency=data["currency"],
        current_rate=data["unit_rate"],
        effective_date=data["effective_date"],
        description=data["description"],
        created_by=current_user.id,
        updated_by=current_user.id,
    )
    db.add(chem)
    db.flush()
    add_mud_chemical_revision(
        db, chem, unit_rate=data["unit_rate"], currency=data["currency"], uom=data["uom"],
        effective_date=data["effective_date"], remarks=data["remarks"], user=current_user,
    )
    db.commit()
    db.refresh(chem)
    log_audit(db, user=current_user, action="CREATE", module=MODULE_NAME, entity_id=chem.id,
              entity_code=chem.chemical_code,
              details=f"Created mud chemical {chem.chemical_code} - {chem.chemical_name} @ {chem.current_rate} {chem.currency or ''}",
              request=request)
    return _build_out(db, chem)


@router.put("/{record_id}", response_model=MudChemicalOut)
def update_chemical(
    record_id: int,
    payload: dict[str, Any],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> MudChemicalOut:
    chem = db.get(MudChemical, record_id)
    if not chem or chem.is_deleted:
        raise HTTPException(status_code=404, detail="Mud chemical not found")

    new_name = str(payload.get("chemical_name") or payload.get("name") or chem.chemical_name).strip()
    if new_name.lower() != chem.chemical_name.lower():
        clash = db.scalar(
            select(MudChemical).where(
                func.lower(MudChemical.chemical_name) == new_name.lower(),
                MudChemical.id != record_id,
                MudChemical.is_deleted == False,
            )
        )
        if clash:
            raise HTTPException(status_code=400, detail=f"Chemical '{new_name}' already exists")
    chem.chemical_name = new_name
    if "part_number" in payload:
        chem.part_number = str(payload.get("part_number") or "").strip() or None
    if "description" in payload:
        chem.description = payload.get("description") or None
    if payload.get("uom") not in (None, ""):
        chem.uom = _resolve_uom(db, payload.get("uom"))

    revision_added = False
    rate_raw = payload.get("unit_rate") if "unit_rate" in payload else payload.get("current_rate")
    if rate_raw not in (None, ""):
        rate = parse_decimal(rate_raw, field="Unit Rate", allow_blank=False)
        if rate is None or rate < 0:
            raise HTTPException(status_code=400, detail="Unit Rate must not be negative")
        currency = _resolve_currency(db, payload.get("currency")) if payload.get("currency") not in (None, "") else chem.currency
        if not currency:
            raise HTTPException(status_code=400, detail="Currency is required")
        eff = parse_date_flexible(payload["effective_date"]) if payload.get("effective_date") not in (None, "") else date.today()
        rev = add_mud_chemical_revision(
            db, chem, unit_rate=rate, currency=currency, uom=chem.uom,
            effective_date=eff, remarks=payload.get("remarks"), user=current_user,
        )
        revision_added = rev is not None
    elif payload.get("currency") not in (None, ""):
        chem.currency = _resolve_currency(db, payload.get("currency"))

    chem.updated_by = current_user.id
    db.commit()
    db.refresh(chem)
    log_audit(
        db, user=current_user,
        action="UPDATE" if not revision_added else "RATE_REVISION",
        module=MODULE_NAME, entity_id=chem.id, entity_code=chem.chemical_code,
        details=(f"Rate revision for {chem.chemical_code}: new rate {chem.current_rate} {chem.currency or ''}"
                 if revision_added else f"Updated mud chemical {chem.chemical_code}"),
        request=request,
    )
    return _build_out(db, chem)


@router.delete("/{record_id}")
def soft_delete_chemical(
    record_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> dict[str, str]:
    chem = db.get(MudChemical, record_id)
    if not chem or chem.is_deleted:
        raise HTTPException(status_code=404, detail="Mud chemical not found")
    chem.is_deleted = True
    chem.deleted_at = datetime.now(UTC)
    db.commit()
    log_audit(db, user=current_user, action="SOFT_DELETE", module=MODULE_NAME, entity_id=chem.id,
              entity_code=chem.chemical_code, details=f"Soft deleted mud chemical {chem.chemical_code}",
              request=request)
    return {"status": "success", "message": "Mud chemical moved to deleted entries"}


@router.post("/{record_id}/restore")
def restore_chemical(
    record_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> dict[str, str]:
    chem = db.get(MudChemical, record_id)
    if not chem or not chem.is_deleted:
        raise HTTPException(status_code=404, detail="Deleted mud chemical not found")
    chem.is_deleted = False
    chem.deleted_at = None
    db.commit()
    log_audit(db, user=current_user, action="RESTORE", module=MODULE_NAME, entity_id=chem.id,
              entity_code=chem.chemical_code, details=f"Restored mud chemical {chem.chemical_code}",
              request=request)
    return {"status": "success", "message": "Mud chemical restored"}


@router.delete("/{record_id}/permanent")
def permanent_delete_chemical(
    record_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> dict[str, str]:
    chem = db.get(MudChemical, record_id)
    if not chem:
        raise HTTPException(status_code=404, detail="Mud chemical not found")
    code = chem.chemical_code
    db.delete(chem)  # cascade removes rate revisions
    db.commit()
    log_audit(db, user=current_user, action="PERMANENT_DELETE", module=MODULE_NAME, entity_id=record_id,
              entity_code=code, details=f"Permanently deleted mud chemical {code} and its rate history",
              request=request)
    return {"status": "success", "message": "Mud chemical permanently deleted"}


# ---------------------------------------------------------------------------
# Bulk import
# ---------------------------------------------------------------------------

IMPORT_TEMPLATE = (
    "chemical_name,part_number,uom,unit_rate,currency,effective_date,description\n"
    "Bentonite,BEN-200,kg,2.50,USD,2026-01-15,Primary viscosifier\n"
    "Barite,BAR-400,kg,3.20,USD,15/02/2026,Weighting agent\n"
)


@router.get("/import-template")
def download_template() -> Response:
    return Response(content=IMPORT_TEMPLATE, media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=mud_chemicals_template.csv"})


@router.post("/import", response_model=BulkImportResponse)
async def import_chemicals(
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
            name = str(row_get(row, "chemical_name", "name", "chemical") or "").strip()
            if not name:
                raise ValueError("Chemical Name is required")
            rate = parse_decimal(row_get(row, "unit_rate", "rate", "price", "unit_rate_as_per_po"),
                                 field="Unit Rate", allow_blank=False)
            if rate is None or rate < 0:
                raise ValueError("Unit Rate is required and must be a number >= 0")
            currency_raw = row_get(row, "currency", "curr", "currency_code")
            if not currency_raw:
                raise ValueError("Currency is required")
            currency = _resolve_currency(db, currency_raw)
            uom = _resolve_uom(db, row_get(row, "uom", "unit", "unit_of_measure"))
            eff = parse_date_flexible(row_get(row, "effective_date", "date", "eff_date")) or date.today()
            part = row_get(row, "part_number", "part_no", "pn")
            desc = row_get(row, "description", "desc", "remarks")

            existing = db.scalar(
                select(MudChemical).where(func.lower(MudChemical.chemical_name) == name.lower())
            )
            if existing:
                if existing.is_deleted:
                    existing.is_deleted = False
                    existing.deleted_at = None
                existing.part_number = str(part).strip() if part else existing.part_number
                existing.uom = uom or existing.uom
                existing.description = str(desc) if desc else existing.description
                add_mud_chemical_revision(
                    db, existing, unit_rate=rate, currency=currency, uom=existing.uom,
                    effective_date=eff, user=current_user,
                )
                existing.updated_by = current_user.id
            else:
                chem = MudChemical(
                    chemical_code=_next_code(db),
                    part_number=str(part).strip() if part else None,
                    chemical_name=name,
                    uom=uom,
                    currency=currency,
                    current_rate=rate,
                    effective_date=eff,
                    description=str(desc) if desc else None,
                    created_by=current_user.id,
                    updated_by=current_user.id,
                )
                db.add(chem)
                db.flush()
                add_mud_chemical_revision(
                    db, chem, unit_rate=rate, currency=currency, uom=uom,
                    effective_date=eff, user=current_user,
                )
            imported += 1
            db.flush()
        except Exception as exc:
            errors.append(f"Row {r_num}: {exc}")

    db.commit()
    log_audit(db, user=current_user, action="BULK_IMPORT", module=MODULE_NAME,
              details=f"Imported {imported} mud chemicals with {len(errors)} errors from {filename}",
              request=request)
    return BulkImportResponse(imported_count=imported, error_count=len(errors),
                              errors=errors[:30], success=not errors)
