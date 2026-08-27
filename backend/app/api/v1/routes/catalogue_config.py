"""Catalogue configuration: user-configurable dropdown lists and the fixed
Consumables subcategory directory (Mud Chemicals / Cement Additives / Fuel /
Drill Bits).
"""

import contextlib
import re
from datetime import UTC, date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db
from app.models.catalogue import (
    CatalogueConfig,
    ConsumableSubcategory,
    DrillBit,
    DrillBitRate,
    MudChemical,
    MudChemicalRate,
)
from app.models.user import User
from app.schemas.catalogue import CatalogueConfigOut, ConsumableSubcategoryOut, MudChemicalRateOut
from app.schemas.master_data import BulkImportResponse
from app.services.audit import log_audit
from app.services.import_helpers import spreadsheet_response

router = APIRouter(prefix="/catalogue", tags=["catalogue-config"])

# Config types the UI exposes "manage" dialogs for. Keeping this server-side
# means new dropdown types only need an entry here.
CONFIG_TYPES: dict[str, str] = {
    "bit_type": "Drill Bit Types",
    "bit_manufacturer": "Drill Bit Manufacturers",
    "tangible_category": "Tangible Categories",
    "tangible_subcategory": "Tangible Subcategories",
    "tangible_manufacturer": "Tangible Manufacturers",
}

MODULE_NAME = "Dropdown Lists"


def _split_values(value: str) -> list[str]:
    """Split a newline/comma/semicolon separated textarea into trimmed values."""

    parts = re.split(r"[\n,;]+", value)
    return [p.strip() for p in parts if p.strip()]


# ---------------------------------------------------------------------------
# Consumable subcategories (fixed directory)
# ---------------------------------------------------------------------------


@router.get("/consumable-subcategories", response_model=list[ConsumableSubcategoryOut])
def list_subcategories(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[ConsumableSubcategory]:
    """List the consumable subcategories (seeded by migration)."""

    stmt = select(ConsumableSubcategory).where(
        ConsumableSubcategory.is_deleted == False
    ).order_by(ConsumableSubcategory.sort_order, ConsumableSubcategory.id)
    return list(db.scalars(stmt).all())


# ---------------------------------------------------------------------------
# Combined Consumables rate-revision history (Mud Chemicals + Drill Bits)
# ---------------------------------------------------------------------------


def _consumable_rate_rows(db: Session) -> list[MudChemicalRateOut]:
    out: list[MudChemicalRateOut] = []
    chem_rows = db.execute(
        select(MudChemicalRate, MudChemical)
        .join(MudChemical, MudChemical.id == MudChemicalRate.chemical_id)
        .where(MudChemicalRate.is_deleted == False, MudChemical.is_deleted == False)
    ).all()
    for rate, chem in chem_rows:
        out.append(MudChemicalRateOut(
            id=rate.id, chemical_id=rate.chemical_id, item_kind="Mud Chemical",
            item_code=chem.chemical_code, item_name=chem.chemical_name,
            unit_rate=rate.unit_rate, previous_rate=rate.previous_rate, currency=rate.currency,
            uom=rate.uom, effective_date=rate.effective_date, revision_number=rate.revision_number,
            remarks=rate.remarks, created_at=rate.created_at,
        ))
    bit_rows = db.execute(
        select(DrillBitRate, DrillBit)
        .join(DrillBit, DrillBit.id == DrillBitRate.bit_id)
        .where(DrillBitRate.is_deleted == False, DrillBit.is_deleted == False)
    ).all()
    for rate, bit in bit_rows:
        out.append(MudChemicalRateOut(
            id=rate.id, bit_id=rate.bit_id, item_kind="Drill Bit",
            item_code=bit.bit_code, item_name=bit.bit_name,
            unit_rate_po=rate.unit_rate_po, cost_uplift=rate.cost_uplift, final_cost=rate.final_cost,
            currency=rate.currency, effective_date=rate.effective_date,
            revision_number=rate.revision_number, po_number=rate.po_number,
            remarks=rate.remarks, created_at=rate.created_at,
        ))
    out.sort(key=lambda r: (r.effective_date or date.min, r.revision_number), reverse=True)
    return out


@router.get("/consumables-rate-history", response_model=list[MudChemicalRateOut])
def consumables_rate_history(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[MudChemicalRateOut]:
    """All consumable rate revisions (Mud Chemicals + Drill Bits), latest first."""

    return _consumable_rate_rows(db)


@router.get("/consumables-rate-history/export")
def export_consumables_rate_history(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
    format: str = Query("xlsx", pattern="^(xlsx|csv)$"),
) -> Response:
    rows = _consumable_rate_rows(db)
    log_audit(db, user=current_user, action="EXPORT", module="Consumable Rate Revisions",
              details=f"Exported {len(rows)} consumable rate revisions as {format}", request=request)
    headers = ["item_kind", "item_code", "item_name", "revision_number", "effective_date",
               "previous_rate", "unit_rate", "unit_rate_po", "cost_uplift", "final_cost",
               "currency", "uom", "po_number", "remarks"]
    data = [
        [r.item_kind, r.item_code, r.item_name, r.revision_number,
         r.effective_date.isoformat() if r.effective_date else "",
         str(r.previous_rate) if r.previous_rate is not None else "",
         str(r.unit_rate) if r.unit_rate is not None else "",
         str(r.unit_rate_po) if r.unit_rate_po is not None else "",
         f"{r.cost_uplift}%" if r.cost_uplift is not None else "",
         str(r.final_cost) if r.final_cost is not None else "",
         r.currency or "", r.uom or "", r.po_number or "", r.remarks or ""]
        for r in rows
    ]
    return spreadsheet_response(data, headers, "consumables_rate_history", format)


# ---------------------------------------------------------------------------
# Configurable dropdown lists
# ---------------------------------------------------------------------------


@router.get("/configs/{config_type}", response_model=list[CatalogueConfigOut])
def list_configs(
    config_type: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    include_deleted: bool = False,
) -> list[CatalogueConfig]:
    """List values for one configurable dropdown."""

    if config_type not in CONFIG_TYPES:
        raise HTTPException(status_code=404, detail=f"Config type '{config_type}' not found")
    stmt = select(CatalogueConfig).where(CatalogueConfig.config_type == config_type)
    if not include_deleted:
        stmt = stmt.where(CatalogueConfig.is_deleted == False)
    stmt = stmt.order_by(CatalogueConfig.sort_order, func.lower(CatalogueConfig.value))
    return list(db.scalars(stmt).all())


@router.post("/configs/{config_type}", response_model=CatalogueConfigOut)
def create_config(
    config_type: str,
    payload: dict[str, Any],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> CatalogueConfig:
    """Add a value to a configurable dropdown (duplicates are rejected)."""

    if config_type not in CONFIG_TYPES:
        raise HTTPException(status_code=404, detail=f"Config type '{config_type}' not found")
    value = str(payload.get("value") or "").strip()
    if not value:
        raise HTTPException(status_code=400, detail="Value is required")

    existing = db.scalar(
        select(CatalogueConfig).where(
            CatalogueConfig.config_type == config_type,
            func.lower(CatalogueConfig.value) == value.lower(),
        )
    )
    if existing and not existing.is_deleted:
        raise HTTPException(status_code=400, detail=f"'{value}' already exists in {CONFIG_TYPES[config_type]}")
    if existing and existing.is_deleted:
        existing.is_deleted = False
        existing.deleted_at = None
        existing.is_active = True
        existing.updated_by = current_user.id
        db.commit()
        db.refresh(existing)
        log_audit(
            db, user=current_user, action="RESTORE", module=MODULE_NAME,
            entity_id=existing.id, entity_code=value,
            details=f"Restored dropdown value {value} ({config_type})", request=request,
        )
        return existing

    max_order = db.scalar(
        select(func.max(CatalogueConfig.sort_order)).where(CatalogueConfig.config_type == config_type)
    )
    instance = CatalogueConfig(
        config_type=config_type,
        value=value,
        sort_order=(max_order or 0) + 1,
        created_by=current_user.id,
        updated_by=current_user.id,
    )
    db.add(instance)
    db.commit()
    db.refresh(instance)
    log_audit(
        db, user=current_user, action="CREATE", module=MODULE_NAME,
        entity_id=instance.id, entity_code=value,
        details=f"Added dropdown value '{value}' to {CONFIG_TYPES[config_type]}", request=request,
    )
    return instance


@router.put("/configs/{config_type}/{record_id}", response_model=CatalogueConfigOut)
def update_config(
    config_type: str,
    record_id: int,
    payload: dict[str, Any],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> CatalogueConfig:
    """Rename a dropdown value (duplicate names are rejected)."""

    instance = db.get(CatalogueConfig, record_id)
    if not instance or instance.config_type != config_type or instance.is_deleted:
        raise HTTPException(status_code=404, detail="Dropdown value not found")
    new_value = str(payload.get("value") or "").strip()
    if not new_value:
        raise HTTPException(status_code=400, detail="Value is required")
    if new_value.lower() != instance.value.lower():
        clash = db.scalar(
            select(CatalogueConfig).where(
                CatalogueConfig.config_type == config_type,
                func.lower(CatalogueConfig.value) == new_value.lower(),
                CatalogueConfig.id != record_id,
            )
        )
        if clash:
            raise HTTPException(status_code=400, detail=f"'{new_value}' already exists in this list")
    old_value = instance.value
    instance.value = new_value
    if "is_active" in payload:
        instance.is_active = bool(payload["is_active"])
    if "sort_order" in payload and payload["sort_order"] is not None:
        with contextlib.suppress(TypeError, ValueError):
            instance.sort_order = int(payload["sort_order"])
    instance.updated_by = current_user.id
    db.commit()
    db.refresh(instance)
    log_audit(
        db, user=current_user, action="UPDATE", module=MODULE_NAME,
        entity_id=instance.id, entity_code=new_value,
        details=f"Renamed dropdown value '{old_value}' to '{new_value}' ({config_type})", request=request,
    )
    return instance


@router.delete("/configs/{config_type}/{record_id}")
def soft_delete_config(
    config_type: str,
    record_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> dict[str, str]:
    """Soft delete a dropdown value (system-seeded values cannot be removed)."""

    instance = db.get(CatalogueConfig, record_id)
    if not instance or instance.config_type != config_type:
        raise HTTPException(status_code=404, detail="Dropdown value not found")
    if instance.is_deleted:
        raise HTTPException(status_code=404, detail="Dropdown value not found")
    if instance.system_seeded:
        raise HTTPException(status_code=400, detail="Built-in values cannot be deleted")
    instance.is_deleted = True
    instance.deleted_at = datetime.now(UTC)
    instance.updated_by = current_user.id
    db.commit()
    log_audit(
        db, user=current_user, action="SOFT_DELETE", module=MODULE_NAME,
        entity_id=instance.id, entity_code=instance.value,
        details=f"Removed dropdown value '{instance.value}' from {CONFIG_TYPES[config_type]}", request=request,
    )
    return {"status": "success", "message": "Dropdown value moved to deleted entries"}


@router.post("/configs/{config_type}/{record_id}/restore")
def restore_config(
    config_type: str,
    record_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> dict[str, str]:
    instance = db.get(CatalogueConfig, record_id)
    if not instance or instance.config_type != config_type or not instance.is_deleted:
        raise HTTPException(status_code=404, detail="Deleted dropdown value not found")
    instance.is_deleted = False
    instance.deleted_at = None
    instance.updated_by = current_user.id
    db.commit()
    log_audit(
        db, user=current_user, action="RESTORE", module=MODULE_NAME,
        entity_id=instance.id, entity_code=instance.value,
        details=f"Restored dropdown value '{instance.value}' ({config_type})", request=request,
    )
    return {"status": "success", "message": "Dropdown value restored"}


@router.delete("/configs/{config_type}/{record_id}/permanent")
def permanent_delete_config(
    config_type: str,
    record_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> dict[str, str]:
    instance = db.get(CatalogueConfig, record_id)
    if not instance or instance.config_type != config_type:
        raise HTTPException(status_code=404, detail="Dropdown value not found")
    value = instance.value
    db.delete(instance)
    db.commit()
    log_audit(
        db, user=current_user, action="PERMANENT_DELETE", module=MODULE_NAME,
        entity_id=record_id, entity_code=value,
        details=f"Permanently deleted dropdown value '{value}' ({config_type})", request=request,
    )
    return {"status": "success", "message": "Dropdown value permanently deleted"}


@router.get("/configs-deleted", response_model=list[CatalogueConfigOut])
def list_deleted_configs(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[CatalogueConfig]:
    """Trash view: all soft-deleted dropdown values across config types."""

    stmt = select(CatalogueConfig).where(
        CatalogueConfig.is_deleted == True
    ).order_by(CatalogueConfig.deleted_at.desc())
    return list(db.scalars(stmt).all())


@router.post("/configs/bulk", response_model=BulkImportResponse)
def bulk_add_configs(
    config_type: str,
    payload: dict[str, Any],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> BulkImportResponse:
    """Bulk-add a list of dropdown values (used by the manage dialog)."""

    if config_type not in CONFIG_TYPES:
        raise HTTPException(status_code=404, detail=f"Config type '{config_type}' not found")
    values = payload.get("values") or []
    if isinstance(values, str):
        values = _split_values(values)
    imported = 0
    errors: list[str] = []
    existing_lower = {
        str(v).lower()
        for v in db.scalars(
            select(CatalogueConfig.value).where(CatalogueConfig.config_type == config_type)
        ).all()
    }
    max_order = db.scalar(
        select(func.max(CatalogueConfig.sort_order)).where(CatalogueConfig.config_type == config_type)
    ) or 0
    seen: set[str] = set()
    for i, raw in enumerate(values, start=1):
        value = str(raw or "").strip()
        if not value:
            continue
        key = value.lower()
        if key in existing_lower or key in seen:
            errors.append(f"Item {i}: '{value}' is a duplicate and was skipped")
            continue
        seen.add(key)
        max_order += 1
        db.add(CatalogueConfig(
            config_type=config_type,
            value=value,
            sort_order=max_order,
            created_by=current_user.id,
            updated_by=current_user.id,
        ))
        imported += 1
    db.commit()
    log_audit(
        db, user=current_user, action="BULK_IMPORT", module=MODULE_NAME,
        details=f"Added {imported} dropdown values to {CONFIG_TYPES[config_type]}", request=request,
    )
    return BulkImportResponse(
        imported_count=imported, error_count=len(errors), errors=errors[:30], success=not errors
    )
