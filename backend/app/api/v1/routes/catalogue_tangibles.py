"""Tangibles catalogue API.

Scope (Drilling / Completion / Others) is a fixed dropdown; Category,
Subcategory and Manufacturer are user-configurable lists managed on the page.
Final Cost = Unit Rate as per PO x Cost Uplift %. Rate changes append
revisions to the rate-revision history tab. Full common template: CRUD +
soft delete + bulk import + export + rate-history export, all audited.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db
from app.models.catalogue import CatalogueConfig, Tangible, TangibleRate
from app.models.master_data import Currency, UnitOfMeasurement
from app.models.user import User
from app.schemas.catalogue import MudChemicalRateOut, TangibleOut
from app.schemas.master_data import BulkImportResponse
from app.services.audit import log_audit
from app.services.catalogue_rates import add_tangible_revision
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

router = APIRouter(prefix="/catalogue/tangibles", tags=["catalogue-tangibles"])

MODULE_NAME = "Tangibles"
CODE_PREFIX = "TNG"

SCOPES = {"Drilling", "Completion", "Others"}
CONFIG_CATEGORY = "tangible_category"
CONFIG_SUBCATEGORY = "tangible_subcategory"
CONFIG_MANUFACTURER = "tangible_manufacturer"


def _next_code(db: Session) -> str:
    highest = 0
    for code in db.scalars(select(Tangible.tangible_code)).all():
        digits = "".join(ch for ch in str(code) if ch.isdigit())
        if digits:
            highest = max(highest, int(digits))
    return f"{CODE_PREFIX}-{highest + 1:04d}"


def _normalize_scope(value: Any) -> str:
    val = str(value or "").strip().lower()
    for scope in SCOPES:
        if val == scope.lower():
            return scope
    if val in {"other", "misc", "miscellaneous"}:
        return "Others"
    raise ValueError(f"Scope must be one of {', '.join(sorted(SCOPES))} (got '{value}')")


def _config_values(db: Session, config_type: str) -> list[str]:
    rows = db.scalars(
        select(CatalogueConfig.value)
        .where(CatalogueConfig.config_type == config_type,
               CatalogueConfig.is_deleted == False,
               CatalogueConfig.is_active == True)
        .order_by(CatalogueConfig.sort_order, func.lower(CatalogueConfig.value))
    ).all()
    return [str(v) for v in rows]


def _resolve_config(
    db: Session,
    config_type: str,
    value: Any,
    *,
    create_if_missing: bool = False,
    parent_value: str | None = None,
) -> str:
    """Resolve a configured dropdown value, optionally within a parent bucket.

    When ``parent_value`` is given, rows under that parent are preferred;
    legacy rows without a parent still match so values created before the
    category dependency keep working.
    """

    val = str(value or "").strip()
    if not val:
        raise ValueError("Value is required")
    base = select(CatalogueConfig).where(
        CatalogueConfig.config_type == config_type,
        func.lower(CatalogueConfig.value) == val.lower(),
    )
    match = None
    if parent_value is not None:
        match = db.scalar(base.where(CatalogueConfig.parent_value == parent_value))
    if match is None:
        match = db.scalar(base.where(CatalogueConfig.parent_value.is_(None)))
    if match is None and parent_value is not None and not create_if_missing:
        # A same-named value that belongs to a different category is not a
        # valid pick — surface exactly which category owns it.
        other = db.scalar(base.where(CatalogueConfig.parent_value != parent_value))
        if other and not other.is_deleted:
            raise ValueError(
                f"'{val}' belongs to the '{other.parent_value}' category — "
                f"pick a subcategory configured under '{parent_value}'"
            )
    if match:
        if match.is_deleted:
            match.is_deleted = False
            match.deleted_at = None
        return match.value
    if create_if_missing:
        parent_bucket = (
            CatalogueConfig.parent_value == parent_value
            if parent_value is not None
            else CatalogueConfig.parent_value.is_(None)
        )
        max_order = db.scalar(select(func.max(CatalogueConfig.sort_order)).where(
            CatalogueConfig.config_type == config_type,
            parent_bucket,
        )) or 0
        db.add(CatalogueConfig(
            config_type=config_type, value=val, parent_value=parent_value, sort_order=max_order + 1,
        ))
        db.flush()
        return val
    known = ", ".join(_config_values(db, config_type)) or "none yet — add one via Manage"
    raise ValueError(f"'{val}' is not in the configured list ({known})")


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


def _build_out(db: Session, tng: Tangible) -> TangibleOut:
    rates = db.scalars(
        select(TangibleRate)
        .where(TangibleRate.tangible_id == tng.id, TangibleRate.is_deleted == False)
        .order_by(TangibleRate.revision_number.desc())
    ).all()
    latest = rates[0] if rates else None
    previous_final = Decimal("0")
    if latest and latest.revision_number > 1:
        prev = db.scalar(
            select(TangibleRate).where(
                TangibleRate.tangible_id == tng.id,
                TangibleRate.revision_number == latest.revision_number - 1,
            )
        )
        previous_final = prev.final_cost if prev else Decimal("0")
    rate_outs = [
        MudChemicalRateOut(
            id=r.id, tangible_id=r.tangible_id, item_kind="Tangible",
            item_code=tng.tangible_code, item_name=tng.tangible_name,
            unit_rate_po=r.unit_rate_po, cost_uplift=r.cost_uplift, final_cost=r.final_cost,
            currency=r.currency, effective_date=r.effective_date, revision_number=r.revision_number,
            po_number=r.po_number, remarks=r.remarks, is_deleted=r.is_deleted, created_at=r.created_at,
        )
        for r in rates
    ]
    return TangibleOut(
        id=tng.id, tangible_code=tng.tangible_code, tangible_scope=tng.tangible_scope,
        category=tng.category, subcategory=tng.subcategory, manufacturer=tng.manufacturer,
        po_number=tng.po_number, tangible_name=tng.tangible_name, uom=tng.uom, currency=tng.currency,
        unit_rate_po=tng.unit_rate_po or Decimal("0"), cost_uplift=tng.cost_uplift or Decimal("100"),
        final_cost=tng.final_cost or Decimal("0"), previous_final_cost=previous_final,
        effective_date=tng.effective_date, description=tng.description, remarks=tng.remarks,
        is_deleted=tng.is_deleted, deleted_at=tng.deleted_at,
        created_at=tng.created_at, updated_at=tng.updated_at, rates=rate_outs,
    )


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


@router.get("")
def list_tangibles(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    search: str | None = None,
    scope: str | None = None,
    category: str | None = None,
) -> list[TangibleOut]:
    stmt = select(Tangible).where(Tangible.is_deleted == False)
    if scope:
        stmt = stmt.where(Tangible.tangible_scope == scope)
    if category:
        stmt = stmt.where(Tangible.category == category)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            or_(Tangible.tangible_name.ilike(like), Tangible.tangible_code.ilike(like),
                Tangible.po_number.ilike(like))
        )
    stmt = stmt.order_by(Tangible.id.desc())
    return [_build_out(db, t) for t in db.scalars(stmt).all()]


@router.get("/dropdown-options")
def dropdown_options(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Dropdown sources for the tangibles grid.

    Subcategories are dependents of the category, so each entry carries the
    category it was configured under (``category`` is null for legacy values
    created before the dependency — those stay available everywhere).
    """

    sub_rows = db.scalars(
        select(CatalogueConfig).where(
            CatalogueConfig.config_type == CONFIG_SUBCATEGORY,
            CatalogueConfig.is_deleted == False,
            CatalogueConfig.is_active == True,
        ).order_by(CatalogueConfig.sort_order, func.lower(CatalogueConfig.value))
    ).all()
    return {
        "scopes": sorted(SCOPES),
        "categories": _config_values(db, CONFIG_CATEGORY),
        "subcategories": [
            {"value": str(row.value), "category": row.parent_value}
            for row in sub_rows
        ],
        "manufacturers": _config_values(db, CONFIG_MANUFACTURER),
    }


@router.get("/deleted")
def list_deleted_tangibles(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[TangibleOut]:
    stmt = select(Tangible).where(Tangible.is_deleted == True).order_by(Tangible.deleted_at.desc())
    return [_build_out(db, t) for t in db.scalars(stmt).all()]


@router.get("/rate-history")
def rate_history(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    tangible_id: int | None = None,
) -> list[MudChemicalRateOut]:
    stmt = (
        select(TangibleRate, Tangible)
        .join(Tangible, Tangible.id == TangibleRate.tangible_id)
        .where(TangibleRate.is_deleted == False, Tangible.is_deleted == False)
        .order_by(TangibleRate.effective_date.desc(), TangibleRate.revision_number.desc())
    )
    if tangible_id:
        stmt = stmt.where(TangibleRate.tangible_id == tangible_id)
    out: list[MudChemicalRateOut] = []
    for rate, tng in db.execute(stmt).all():
        out.append(MudChemicalRateOut(
            id=rate.id, tangible_id=rate.tangible_id, item_kind="Tangible",
            item_code=tng.tangible_code, item_name=tng.tangible_name,
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
        select(TangibleRate, Tangible)
        .join(Tangible, Tangible.id == TangibleRate.tangible_id)
        .where(TangibleRate.is_deleted == False)
        .order_by(Tangible.tangible_code, TangibleRate.revision_number)
    )
    records = db.execute(stmt).all()
    log_audit(db, user=current_user, action="EXPORT", module=MODULE_NAME,
              details=f"Exported {len(records)} tangible rate revisions as {format}", request=request)
    headers = ["tangible_code", "tangible_name", "scope", "revision_number", "effective_date",
               "unit_rate_po", "cost_uplift", "final_cost", "currency", "po_number", "remarks"]
    rows = [
        [tng.tangible_code, tng.tangible_name, tng.tangible_scope, rate.revision_number,
         rate.effective_date.isoformat() if rate.effective_date else "",
         str(rate.unit_rate_po), str(rate.cost_uplift), str(rate.final_cost),
         rate.currency or "", rate.po_number or "", rate.remarks or ""]
        for rate, tng in records
    ]
    return spreadsheet_response(rows, headers, "tangible_rate_history", format)


@router.get("/export")
def export_tangibles(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
    format: str = Query("xlsx", pattern="^(xlsx|csv)$"),
) -> Response:
    records = db.scalars(
        select(Tangible).where(Tangible.is_deleted == False).order_by(Tangible.tangible_code)
    ).all()
    log_audit(db, user=current_user, action="EXPORT", module=MODULE_NAME,
              details=f"Exported {len(records)} tangibles as {format}", request=request)
    headers = ["tangible_code", "tangible_scope", "category", "subcategory", "manufacturer",
               "po_number", "tangible_name", "uom", "unit_rate_po", "cost_uplift", "final_cost",
               "currency", "effective_date", "description", "remarks"]
    rows = [
        [t.tangible_code, t.tangible_scope, t.category, t.subcategory, t.manufacturer,
         t.po_number or "", t.tangible_name, t.uom or "", str(t.unit_rate_po), str(t.cost_uplift),
         str(t.final_cost), t.currency or "",
         t.effective_date.isoformat() if t.effective_date else "",
         t.description or "", t.remarks or ""]
        for t in records
    ]
    return spreadsheet_response(rows, headers, "tangibles_export", format)


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def _parse_payload(db: Session, payload: dict[str, Any], *, create: bool) -> dict[str, Any]:
    name = str(payload.get("tangible_name") or payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Tangible Name is required")

    scope_raw = payload.get("tangible_scope") or payload.get("scope")
    if create and not scope_raw:
        raise HTTPException(status_code=400, detail="Tangible Scope is required (Drilling / Completion / Others)")
    try:
        scope = _normalize_scope(scope_raw) if scope_raw else None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    def require_config(field_label: str, config_type: str, value: Any) -> str:
        if create and not str(value or "").strip():
            raise HTTPException(status_code=400, detail=f"{field_label} is required")
        if not str(value or "").strip():
            return ""
        try:
            return _resolve_config(db, config_type, value)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    category = require_config("Category", CONFIG_CATEGORY, payload.get("category"))
    # Subcategories depend on the category: resolve the subcategory within the
    # selected category's bucket (legacy parent-less values still match).
    sub_raw = payload.get("subcategory")
    if create and not str(sub_raw or "").strip():
        raise HTTPException(status_code=400, detail="Subcategory is required")
    if str(sub_raw or "").strip():
        if not category:
            raise HTTPException(
                status_code=400,
                detail="Select the category first — subcategories depend on it",
            )
        try:
            subcategory = _resolve_config(db, CONFIG_SUBCATEGORY, sub_raw, parent_value=category)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    else:
        subcategory = ""
    manufacturer = require_config("Manufacturer", CONFIG_MANUFACTURER, payload.get("manufacturer"))

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
        "scope": scope,
        "category": category,
        "subcategory": subcategory,
        "manufacturer": manufacturer,
        "po_number": str(payload.get("po_number") or "").strip() or None,
        "uom": _resolve_uom(db, payload.get("uom")),
        "unit_rate_po": rate if rate is not None else Decimal("0"),
        "cost_uplift": uplift,
        "final_cost": final_cost(rate if rate is not None else Decimal("0"), uplift),
        "currency": currency,
        "effective_date": eff,
        "description": payload.get("description") or None,
        "remarks": payload.get("remarks") or None,
    }


@router.post("")
def create_tangible(
    payload: dict[str, Any],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> TangibleOut:
    data = _parse_payload(db, payload, create=True)
    dup = db.scalar(
        select(Tangible).where(
            func.lower(Tangible.tangible_name) == data["name"].lower(),
            Tangible.is_deleted == False,
        )
    )
    if dup:
        raise HTTPException(status_code=400,
                            detail=f"Tangible '{data['name']}' already exists — code {dup.tangible_code}")

    tng = Tangible(
        tangible_code=_next_code(db),
        tangible_scope=data["scope"], category=data["category"], subcategory=data["subcategory"],
        manufacturer=data["manufacturer"], po_number=data["po_number"], tangible_name=data["name"],
        uom=data["uom"], currency=data["currency"], unit_rate_po=data["unit_rate_po"],
        cost_uplift=data["cost_uplift"], final_cost=data["final_cost"],
        effective_date=data["effective_date"], description=data["description"], remarks=data["remarks"],
        created_by=current_user.id, updated_by=current_user.id,
    )
    db.add(tng)
    db.flush()
    add_tangible_revision(
        db, tng, unit_rate_po=data["unit_rate_po"], cost_uplift=data["cost_uplift"],
        currency=data["currency"], effective_date=data["effective_date"],
        po_number=data["po_number"], remarks=data["remarks"], user=current_user,
    )
    db.commit()
    db.refresh(tng)
    log_audit(db, user=current_user, action="CREATE", module=MODULE_NAME, entity_id=tng.id,
              entity_code=tng.tangible_code,
              details=f"Created tangible {tng.tangible_code} - {tng.tangible_name} final cost {tng.final_cost} {tng.currency or ''}",
              request=request)
    return _build_out(db, tng)


@router.put("/{record_id}")
def update_tangible(
    record_id: int,
    payload: dict[str, Any],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> TangibleOut:
    tng = db.get(Tangible, record_id)
    if not tng or tng.is_deleted:
        raise HTTPException(status_code=404, detail="Tangible not found")

    new_name = str(payload.get("tangible_name") or payload.get("name") or tng.tangible_name).strip()
    if new_name.lower() != tng.tangible_name.lower():
        clash = db.scalar(
            select(Tangible).where(
                func.lower(Tangible.tangible_name) == new_name.lower(),
                Tangible.id != record_id,
                Tangible.is_deleted == False,
            )
        )
        if clash:
            raise HTTPException(status_code=400, detail=f"Tangible '{new_name}' already exists")
    tng.tangible_name = new_name

    if payload.get("tangible_scope") or payload.get("scope"):
        try:
            tng.tangible_scope = _normalize_scope(payload.get("tangible_scope") or payload.get("scope"))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    category_changed = False
    if payload.get("category") not in (None, ""):
        try:
            new_category = _resolve_config(db, CONFIG_CATEGORY, payload["category"])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        category_changed = new_category != tng.category
        tng.category = new_category
    if payload.get("subcategory") not in (None, ""):
        # Subcategory is validated against the row's (possibly just-updated)
        # category so dependents can never drift away from their parent.
        if not tng.category:
            raise HTTPException(
                status_code=400,
                detail="Select the category first — subcategories depend on it",
            )
        try:
            tng.subcategory = _resolve_config(
                db, CONFIG_SUBCATEGORY, payload["subcategory"], parent_value=tng.category,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    elif category_changed and tng.subcategory:
        # Moving a row to another category must not strand a subcategory that
        # belongs to the old one.
        try:
            tng.subcategory = _resolve_config(
                db, CONFIG_SUBCATEGORY, tng.subcategory, parent_value=tng.category,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot switch to '{tng.category}': {exc}",
            ) from exc
    if payload.get("manufacturer") not in (None, ""):
        try:
            tng.manufacturer = _resolve_config(db, CONFIG_MANUFACTURER, payload["manufacturer"])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    if "po_number" in payload:
        tng.po_number = str(payload.get("po_number") or "").strip() or None
    if payload.get("uom") not in (None, ""):
        tng.uom = _resolve_uom(db, payload.get("uom"))
    if "description" in payload:
        tng.description = payload.get("description") or None
    if "remarks" in payload:
        tng.remarks = payload.get("remarks") or None

    revision_added = False
    has_rate = payload.get("unit_rate_po") not in (None, "") or payload.get("unit_rate") not in (None, "")
    if has_rate:
        rate = parse_decimal(
            payload.get("unit_rate_po") if "unit_rate_po" in payload else payload.get("unit_rate"),
            field="Unit Rate as per PO", allow_blank=False)
        if rate is None or rate < 0:
            raise HTTPException(status_code=400, detail="Unit Rate as per PO must be >= 0")
        uplift = parse_uplift(payload.get("cost_uplift"), default=tng.cost_uplift or Decimal("100"))
        currency = tng.currency
        if payload.get("currency") not in (None, ""):
            currency = _resolve_currency(db, payload["currency"])
        if not currency:
            raise HTTPException(status_code=400, detail="Currency is required")
        eff = parse_date_flexible(payload.get("effective_date")) if payload.get("effective_date") not in (None, "") else date.today()
        rev = add_tangible_revision(
            db, tng, unit_rate_po=rate, cost_uplift=uplift, currency=currency,
            effective_date=eff, po_number=tng.po_number,
            remarks=payload.get("remarks") or tng.remarks, user=current_user,
        )
        revision_added = rev is not None
    elif payload.get("cost_uplift") not in (None, ""):
        uplift = parse_uplift(payload.get("cost_uplift"), default=tng.cost_uplift or Decimal("100"))
        rev = add_tangible_revision(
            db, tng, unit_rate_po=tng.unit_rate_po, cost_uplift=uplift, currency=tng.currency,
            effective_date=date.today(), po_number=tng.po_number, remarks=tng.remarks, user=current_user,
        )
        revision_added = rev is not None
    if payload.get("currency") not in (None, "") and not has_rate:
        tng.currency = _resolve_currency(db, payload["currency"])

    tng.updated_by = current_user.id
    db.commit()
    db.refresh(tng)
    log_audit(db, user=current_user,
              action="RATE_REVISION" if revision_added else "UPDATE",
              module=MODULE_NAME, entity_id=tng.id, entity_code=tng.tangible_code,
              details=(f"Rate revision for {tng.tangible_code}: final cost {tng.final_cost} {tng.currency or ''}"
                       if revision_added else f"Updated tangible {tng.tangible_code}"),
              request=request)
    return _build_out(db, tng)


@router.delete("/{record_id}")
def soft_delete_tangible(
    record_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> dict[str, str]:
    tng = db.get(Tangible, record_id)
    if not tng or tng.is_deleted:
        raise HTTPException(status_code=404, detail="Tangible not found")
    tng.is_deleted = True
    tng.deleted_at = datetime.now(UTC)
    db.commit()
    log_audit(db, user=current_user, action="SOFT_DELETE", module=MODULE_NAME, entity_id=tng.id,
              entity_code=tng.tangible_code, details=f"Soft deleted tangible {tng.tangible_code}",
              request=request)
    return {"status": "success", "message": "Tangible moved to deleted entries"}


@router.post("/{record_id}/restore")
def restore_tangible(
    record_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> dict[str, str]:
    tng = db.get(Tangible, record_id)
    if not tng or not tng.is_deleted:
        raise HTTPException(status_code=404, detail="Deleted tangible not found")
    tng.is_deleted = False
    tng.deleted_at = None
    db.commit()
    log_audit(db, user=current_user, action="RESTORE", module=MODULE_NAME, entity_id=tng.id,
              entity_code=tng.tangible_code, details=f"Restored tangible {tng.tangible_code}",
              request=request)
    return {"status": "success", "message": "Tangible restored"}


@router.delete("/{record_id}/permanent")
def permanent_delete_tangible(
    record_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> dict[str, str]:
    tng = db.get(Tangible, record_id)
    if not tng:
        raise HTTPException(status_code=404, detail="Tangible not found")
    code = tng.tangible_code
    db.delete(tng)
    db.commit()
    log_audit(db, user=current_user, action="PERMANENT_DELETE", module=MODULE_NAME, entity_id=record_id,
              entity_code=code, details=f"Permanently deleted tangible {code} and its rate history",
              request=request)
    return {"status": "success", "message": "Tangible permanently deleted"}


# ---------------------------------------------------------------------------
# Bulk import
# ---------------------------------------------------------------------------

IMPORT_HEADERS = [
    "tangible_name", "tangible_scope", "category", "subcategory", "manufacturer",
    "po_number", "uom", "unit_rate_po", "cost_uplift", "currency", "effective_date",
    "description", "remarks",
]


@router.get("/import-template")
def download_template(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    """XLSX template with in-cell dropdowns for scope, category, UOM and currency.

    Download it, fill it with data and upload the same file on the Tangibles
    tab. Subcategories must belong to the row's category — new subcategory
    names are created under that category automatically on import.
    """

    uoms = [str(code) for code in db.scalars(
        select(UnitOfMeasurement.unit_code).where(UnitOfMeasurement.is_deleted == False)
        .order_by(UnitOfMeasurement.unit_code)
    ).all()]
    currencies = [str(code) for code in db.scalars(
        select(Currency.currency_code).where(Currency.is_deleted == False)
        .order_by(Currency.currency_code)
    ).all()]
    return template_xlsx_response(
        "tangibles_template",
        IMPORT_HEADERS,
        sample_rows=[
            ["Casing Pipe 9-5/8", "Drilling", "Casing", "Surface Casing", "Tenaris",
             "PO-2026-10", "m", 120, 100, "USD", "2026-02-10", "Surface casing string", "First order"],
        ],
        dropdowns={
            2: sorted(SCOPES),
            3: _config_values(db, CONFIG_CATEGORY),
            7: uoms,
            10: currencies,
        },
        note=("Fill one tangible per row. Codes are generated automatically; re-importing an "
              "existing tangible name with a new rate appends a rate revision. Each subcategory "
              "must belong to the row's category — new subcategory names are created under that "
              "category automatically."),
    )


@router.post("/import", response_model=BulkImportResponse)
async def import_tangibles(
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
            name = str(row_get(row, "tangible_name", "name") or "").strip()
            if not name:
                raise ValueError("Tangible Name is required")
            scope = _normalize_scope(row_get(row, "tangible_scope", "scope"))
            category = _resolve_config(db, CONFIG_CATEGORY, row_get(row, "category"), create_if_missing=True)
            # The subcategory is linked to the row's category; missing values
            # are created under that category automatically.
            subcategory = _resolve_config(db, CONFIG_SUBCATEGORY, row_get(row, "subcategory", "sub_category"),
                                          create_if_missing=True, parent_value=category)
            manufacturer = _resolve_config(db, CONFIG_MANUFACTURER, row_get(row, "manufacturer", "make"),
                                           create_if_missing=True)
            rate = parse_decimal(row_get(row, "unit_rate_po", "unit_rate", "rate"),
                                 field="Unit Rate as per PO", allow_blank=False)
            if rate is None or rate < 0:
                raise ValueError("Unit Rate as per PO is required and must be >= 0")
            uplift = parse_uplift(row_get(row, "cost_uplift", "uplift"), default=Decimal("100"))
            currency = _resolve_currency(db, row_get(row, "currency", "curr"))
            uom = _resolve_uom(db, row_get(row, "uom", "unit"))
            eff = parse_date_flexible(row_get(row, "effective_date", "date")) or date.today()
            po_number = str(row_get(row, "po_number", "po") or "").strip() or None
            desc = row_get(row, "description", "desc")
            remarks = row_get(row, "remarks", "remark")

            existing = db.scalar(
                select(Tangible).where(func.lower(Tangible.tangible_name) == name.lower())
            )
            if existing:
                if existing.is_deleted:
                    existing.is_deleted = False
                    existing.deleted_at = None
                existing.tangible_scope = scope
                existing.category = category
                existing.subcategory = subcategory
                existing.manufacturer = manufacturer
                existing.po_number = po_number or existing.po_number
                existing.uom = uom or existing.uom
                existing.description = str(desc) if desc else existing.description
                existing.remarks = str(remarks) if remarks else existing.remarks
                add_tangible_revision(
                    db, existing, unit_rate_po=rate, cost_uplift=uplift, currency=currency,
                    effective_date=eff, po_number=po_number,
                    remarks=str(remarks) if remarks else None, user=current_user,
                )
                existing.updated_by = current_user.id
            else:
                tng = Tangible(
                    tangible_code=_next_code(db),
                    tangible_scope=scope, category=category, subcategory=subcategory,
                    manufacturer=manufacturer, po_number=po_number, tangible_name=name, uom=uom,
                    currency=currency, unit_rate_po=rate, cost_uplift=uplift,
                    final_cost=final_cost(rate, uplift), effective_date=eff,
                    description=str(desc) if desc else None,
                    remarks=str(remarks) if remarks else None,
                    created_by=current_user.id, updated_by=current_user.id,
                )
                db.add(tng)
                db.flush()
                add_tangible_revision(
                    db, tng, unit_rate_po=rate, cost_uplift=uplift, currency=currency,
                    effective_date=eff, po_number=po_number,
                    remarks=str(remarks) if remarks else None, user=current_user,
                )
            imported += 1
            db.flush()
        except Exception as exc:
            errors.append(f"Row {r_num}: {exc}")

    db.commit()
    log_audit(db, user=current_user, action="BULK_IMPORT", module=MODULE_NAME,
              details=f"Imported {imported} tangibles with {len(errors)} errors from {filename}",
              request=request)
    return BulkImportResponse(imported_count=imported, error_count=len(errors),
                              errors=errors[:30], success=not errors)
