"""Rig & Well Management API routes.

Provides the common template features (Import XLSX/CSV, XLSX/CSV export,
print-ready data, soft delete → deleted-entries tab → permanent delete, audit
logging and duplicate-code prevention) for Rigs and Wells, plus the well
configuration workflow (sections → phases → days → totals) with explicit
status transitions that are all audit-logged with remarks.

Path ordering note: static paths (``/rigs/dropdown``, ``/rigs/export``,
``/rigs/import-template``, ``/wells/export``, …) are declared before the
``/{record_id}`` routes so FastAPI matches them first.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportArgumentType=false, reportOptionalMemberAccess=false, reportUnknownParameterType=false, reportMissingTypeArgument=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false, reportOptionalIterable=false

import io
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db
from app.models.master_data import HoleSection, Phase
from app.models.rig_well import Rig, Well, WellPhase, WellSection
from app.models.user import User
from app.schemas.master_data import BulkImportResponse
from app.schemas.rig_well import (
    MarkWellIn,
    PhaseOut,
    RigDropdownOut,
    RigOut,
    SectionOut,
    WellConfigurationIn,
    WellConfigurationOut,
    WellOut,
)
from app.services.audit import log_audit
from app.services.import_helpers import read_tabular_file, row_get, template_xlsx_response

router = APIRouter(prefix="/rig-well", tags=["rig-well"])

MODULE_RIGS = "Rigs"
MODULE_WELLS = "Wells"
MODULE_CONFIG = "Well Configuration"

VALID_STATUSES = {"active", "completed"}
VALID_CONFIG_STATUSES = {"draft", "configured"}
DEPTH_UNITS = {"m", "ft"}


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _check_rig_exists(db: Session, rig_id: int) -> Rig:
    rig = db.get(Rig, rig_id)
    if not rig or rig.is_deleted:
        raise HTTPException(status_code=404, detail="Rig not found or deleted")
    return rig


def _well_totals(well: Well) -> tuple[Decimal | None, Decimal]:
    """(total_depth, total_days) for a well.

    Total depth is the ``to_depth`` of the last ordered section; total days is
    the sum of every phase's day count across all sections.
    """
    total_depth: Decimal | None = None
    total_days = Decimal("0")
    for section in well.sections:
        total_depth = section.to_depth
        for phase in section.phases:
            total_days += phase.days
    return total_depth, total_days


def _build_well_out(well: Well) -> WellOut:
    total_depth, total_days = _well_totals(well)
    rig_code = well.rig.rig_code if well.rig else None
    rig_name = well.rig.rig_name if well.rig else None
    return WellOut(
        id=well.id,
        rig_id=well.rig_id,
        well_code=well.well_code or "",
        well_name=well.well_name or "",
        well_location=well.well_location or "",
        block=well.block or "",
        objective=well.objective or "",
        remarks=well.remarks,
        status=well.status or "active",
        config_status=well.config_status or "draft",
        depth_unit=well.depth_unit or "m",
        is_deleted=well.is_deleted,
        deleted_at=well.deleted_at,
        created_at=well.created_at,
        updated_at=well.updated_at,
        rig_code=rig_code,
        rig_name=rig_name,
        rig_display=f"{rig_code} - {rig_name}" if rig_code and rig_name else (rig_code or rig_name),
        total_depth=total_depth,
        total_days=total_days,
        section_count=len(well.sections),
    )


def _build_config_out(well: Well) -> WellConfigurationOut:
    total_depth, total_days = _well_totals(well)
    sections: list[SectionOut] = []
    for section in well.sections:
        phases: list[PhaseOut] = []
        section_days = Decimal("0")
        for phase in section.phases:
            days = phase.days
            section_days += days
            phases.append(
                PhaseOut(
                    id=phase.id,
                    phase_id=phase.phase_id,
                    phase_code=phase.phase.phase_code if phase.phase else None,
                    phase_name=phase.phase.phase_name if phase.phase else None,
                    days=days,
                    remarks=phase.remarks,
                )
            )
        sections.append(
            SectionOut(
                id=section.id,
                section_id=section.section_id,
                section_code=section.section.section_code if section.section else None,
                section_name=section.section.section_name if section.section else None,
                from_depth=section.from_depth,
                to_depth=section.to_depth,
                remarks=section.remarks,
                total_days=section_days,
                phases=phases,
            )
        )
    return WellConfigurationOut(
        well_id=well.id,
        well_code=well.well_code,
        well_name=well.well_name,
        rig_code=well.rig.rig_code if well.rig else None,
        rig_name=well.rig.rig_name if well.rig else None,
        status=well.status,
        config_status=well.config_status,
        depth_unit=well.depth_unit,
        total_depth=total_depth,
        total_days=total_days,
        sections=sections,
    )


def _ensure_well_editable(well: Well) -> None:
    """Reject configuration writes unless the well is active and in draft."""
    if well.status == "completed":
        raise HTTPException(
            status_code=400,
            detail="Well is completed — mark it Active before editing its configuration.",
        )
    if well.config_status != "draft":
        raise HTTPException(
            status_code=400,
            detail="Well is configured — mark it as Draft before editing its configuration.",
        )


# ---------------------------------------------------------------------------
# Rigs
# ---------------------------------------------------------------------------


@router.get("/rigs/dropdown", response_model=list[RigDropdownOut])
def list_rigs_dropdown(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[RigDropdownOut]:
    stmt = select(Rig).where(Rig.is_deleted == False).order_by(Rig.rig_code)
    records = db.scalars(stmt).all()
    return [
        RigDropdownOut(
            id=r.id,
            rig_code=r.rig_code,
            rig_name=r.rig_name,
            display_name=f"{r.rig_code} - {r.rig_name}",
        )
        for r in records
    ]


@router.get("/rigs/deleted", response_model=list[RigOut])
def list_rigs_deleted(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[RigOut]:
    stmt = select(Rig).where(Rig.is_deleted == True).order_by(Rig.deleted_at.desc())
    records = db.scalars(stmt).all()
    out: list[RigOut] = []
    for r in records:
        item = RigOut.model_validate(r)
        item.well_count = len([w for w in r.wells if not w.is_deleted])
        out.append(item)
    return out


@router.get("/rigs", response_model=list[RigOut])
def list_rigs(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    search: str | None = None,
) -> list[RigOut]:
    stmt = select(Rig).where(Rig.is_deleted == False).order_by(Rig.id.desc())
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(Rig.rig_code.ilike(like), Rig.rig_name.ilike(like), Rig.remarks.ilike(like)))
    records = db.scalars(stmt).all()
    out: list[RigOut] = []
    for r in records:
        item = RigOut.model_validate(r)
        item.well_count = len([w for w in r.wells if not w.is_deleted])
        out.append(item)
    return out


@router.post("/rigs", response_model=RigOut)
def create_rig(
    payload: dict[str, Any],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> RigOut:
    code = str(payload.get("rig_code") or payload.get("code") or "").strip()
    name = str(payload.get("rig_name") or payload.get("name") or "").strip()
    if not code:
        raise HTTPException(status_code=400, detail="Rig Code is required")
    if not name:
        raise HTTPException(status_code=400, detail="Rig Name is required")

    existing = db.scalar(select(Rig).where(Rig.rig_code == code))
    if existing and not existing.is_deleted:
        raise HTTPException(status_code=400, detail=f"Rig code '{code}' already exists")
    if existing and existing.is_deleted:
        existing.rig_name = name
        existing.remarks = payload.get("remarks")
        existing.is_deleted = False
        existing.deleted_at = None
        existing.updated_by = current_user.id
        db.commit()
        db.refresh(existing)
        log_audit(
            db, user=current_user, action="RESTORE", module=MODULE_RIGS,
            entity_id=existing.id, entity_code=code,
            details=f"Restored existing deleted rig {code} on create", request=request,
        )
        return RigOut.model_validate(existing)

    instance = Rig(
        rig_code=code,
        rig_name=name,
        remarks=payload.get("remarks"),
        created_by=current_user.id,
        updated_by=current_user.id,
    )
    db.add(instance)
    db.commit()
    db.refresh(instance)
    log_audit(
        db, user=current_user, action="CREATE", module=MODULE_RIGS,
        entity_id=instance.id, entity_code=code,
        details=f"Created rig {code} - {name}", request=request,
    )
    return RigOut.model_validate(instance)


@router.put("/rigs/{record_id}", response_model=RigOut)
def update_rig(
    record_id: int,
    payload: dict[str, Any],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> RigOut:
    instance = db.get(Rig, record_id)
    if not instance or instance.is_deleted:
        raise HTTPException(status_code=404, detail="Rig not found")

    new_code = (payload.get("rig_code") or payload.get("code") or "").strip()
    if new_code and new_code != instance.rig_code:
        existing = db.scalar(select(Rig).where(Rig.rig_code == new_code))
        if existing and existing.id != record_id:
            raise HTTPException(status_code=400, detail=f"Rig code '{new_code}' already exists")
        instance.rig_code = new_code

    if payload.get("rig_name") or payload.get("name"):
        instance.rig_name = str(payload.get("rig_name") or payload.get("name")).strip()
    if "remarks" in payload:
        instance.remarks = payload.get("remarks")

    instance.updated_by = current_user.id
    db.commit()
    db.refresh(instance)
    log_audit(
        db, user=current_user, action="UPDATE", module=MODULE_RIGS,
        entity_id=instance.id, entity_code=instance.rig_code,
        details=f"Updated rig {instance.rig_code}", request=request,
    )
    return RigOut.model_validate(instance)


@router.delete("/rigs/{record_id}")
def soft_delete_rig(
    record_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> dict[str, Any]:
    instance = db.get(Rig, record_id)
    if not instance or instance.is_deleted:
        raise HTTPException(status_code=404, detail="Rig not found")

    active_wells = [w for w in instance.wells if not w.is_deleted]
    if active_wells:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete rig '{instance.rig_code}' — it has {len(active_wells)} active well(s). "
                   "Soft-delete or reassign those wells first.",
        )

    instance.is_deleted = True
    instance.deleted_at = datetime.now(UTC)
    instance.updated_by = current_user.id
    db.commit()
    log_audit(
        db, user=current_user, action="SOFT_DELETE", module=MODULE_RIGS,
        entity_id=instance.id, entity_code=instance.rig_code,
        details=f"Soft deleted rig {instance.rig_code}", request=request,
    )
    return {"status": "success", "message": "Rig moved to deleted entries"}


@router.post("/rigs/{record_id}/restore")
def restore_rig(
    record_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> dict[str, Any]:
    instance = db.get(Rig, record_id)
    if not instance or not instance.is_deleted:
        raise HTTPException(status_code=404, detail="Deleted rig not found")
    instance.is_deleted = False
    instance.deleted_at = None
    instance.updated_by = current_user.id
    db.commit()
    log_audit(
        db, user=current_user, action="RESTORE", module=MODULE_RIGS,
        entity_id=instance.id, entity_code=instance.rig_code,
        details=f"Restored rig {instance.rig_code}", request=request,
    )
    return {"status": "success", "message": "Rig restored"}


@router.delete("/rigs/{record_id}/permanent")
def permanent_delete_rig(
    record_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> dict[str, Any]:
    instance = db.get(Rig, record_id)
    if not instance:
        raise HTTPException(status_code=404, detail="Rig not found")
    code = instance.rig_code
    db.delete(instance)
    db.commit()
    log_audit(
        db, user=current_user, action="PERMANENT_DELETE", module=MODULE_RIGS,
        entity_id=record_id, entity_code=code,
        details=f"Permanently deleted rig {code}", request=request,
    )
    return {"status": "success", "message": "Rig permanently deleted"}


@router.get("/rigs/import-template")
def download_rigs_template(current_user: User = Depends(get_current_user)) -> Response:
    return template_xlsx_response(
        "rigs_template",
        ["rig_code", "rig_name", "remarks"],
        sample_rows=[
            ["RIG001", "Drilling Rig Alpha", "Primary land rig"],
            ["RIG002", "Drilling Rig Bravo", "Offshore jack-up"],
        ],
        note="Keep the header row unchanged; fill one rig per row below it. Codes must be unique.",
    )


@router.post("/rigs/import", response_model=BulkImportResponse)
async def import_rigs(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request = None,
) -> BulkImportResponse:
    contents = await file.read()
    try:
        rows = read_tabular_file(contents, file.filename or "")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    imported = 0
    errors: list[str] = []
    for r_num, row in rows:
        code = str(row_get(row, "rig_code", "code", "rigcode") or "").strip()
        name = str(row_get(row, "rig_name", "name", "rigname") or "").strip()
        remarks = row_get(row, "remarks", "remark") or None
        if not code:
            errors.append(f"Row {r_num}: Missing rig_code")
            continue
        if not name:
            name = code
        existing = db.scalar(select(Rig).where(Rig.rig_code == code))
        if existing:
            existing.rig_name = name
            if remarks:
                existing.remarks = str(remarks)
            existing.is_deleted = False
            existing.deleted_at = None
            existing.updated_by = current_user.id
            imported += 1
        else:
            try:
                db.add(Rig(
                    rig_code=code, rig_name=name,
                    remarks=str(remarks) if remarks else None,
                    created_by=current_user.id, updated_by=current_user.id,
                ))
                imported += 1
            except Exception as exc:  # pragma: no cover - defensive
                errors.append(f"Row {r_num} ({code}): {exc}")
    db.commit()
    log_audit(
        db, user=current_user, action="BULK_IMPORT", module=MODULE_RIGS,
        details=f"Imported {imported} rigs with {len(errors)} errors from {file.filename}", request=request,
    )
    return BulkImportResponse(imported_count=imported, error_count=len(errors), errors=errors[:30], success=not errors)


@router.get("/rigs/export")
def export_rigs(
    format: str = Query("xlsx", pattern="^(xlsx|csv)$"),
    include_deleted: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request = None,
) -> Response:
    stmt = select(Rig)
    if not include_deleted:
        stmt = stmt.where(Rig.is_deleted == False)
    records = db.scalars(stmt).all()
    log_audit(
        db, user=current_user, action="EXPORT", module=MODULE_RIGS,
        details=f"Exported {len(records)} rigs as {format}", request=request,
    )
    headers = ["rig_code", "rig_name", "remarks", "is_deleted", "created_at"]
    data = [
        [r.rig_code, r.rig_name, r.remarks or "", r.is_deleted, r.created_at.isoformat() if r.created_at else ""]
        for r in records
    ]
    return _spreadsheet(data, headers, "rigs", format)


def _spreadsheet(data: list[list[Any]], headers: list[str], filename: str, fmt: str) -> Response:
    import csv

    if fmt == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        writer.writerows(data)
        return Response(
            content=output.getvalue(), media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}.csv"},
        )
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = filename[:31]
    ws.append(headers)
    for row in data:
        ws.append(row)
    bio = io.BytesIO()
    wb.save(bio)
    bio.seek(0)
    return Response(
        content=bio.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}.xlsx"},
    )


# ---------------------------------------------------------------------------
# Wells
# ---------------------------------------------------------------------------


@router.get("/wells/deleted", response_model=list[WellOut])
def list_wells_deleted(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[WellOut]:
    stmt = select(Well).where(Well.is_deleted == True).order_by(Well.deleted_at.desc())
    return [_build_well_out(w) for w in db.scalars(stmt).all()]


@router.get("/wells", response_model=list[WellOut])
def list_wells(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    search: str | None = None,
    rig_id: int | None = None,
    status: str | None = None,
    config_status: str | None = None,
    block: str | None = None,
) -> list[WellOut]:
    stmt = select(Well).where(Well.is_deleted == False).order_by(Well.id.desc())
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            or_(
                Well.well_code.ilike(like),
                Well.well_name.ilike(like),
                Well.well_location.ilike(like),
                Well.block.ilike(like),
                Well.objective.ilike(like),
                Well.remarks.ilike(like),
            )
        )
    if rig_id:
        stmt = stmt.where(Well.rig_id == rig_id)
    if status:
        stmt = stmt.where(Well.status == status)
    if config_status:
        stmt = stmt.where(Well.config_status == config_status)
    if block:
        stmt = stmt.where(Well.block == block)
    return [_build_well_out(w) for w in db.scalars(stmt).all()]


@router.post("/wells", response_model=WellOut)
def create_well(
    payload: dict[str, Any],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> WellOut:
    rig_id = payload.get("rig_id")
    if not rig_id:
        raise HTTPException(status_code=400, detail="Select a Rig first (Rig is mandatory)")
    try:
        rig_id = int(rig_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid Rig selection") from exc
    _check_rig_exists(db, rig_id)

    code = str(payload.get("well_code") or payload.get("code") or "").strip()
    name = str(payload.get("well_name") or payload.get("name") or "").strip()
    location = str(payload.get("well_location") or "").strip()
    block = str(payload.get("block") or "").strip()
    objective = str(payload.get("objective") or "").strip()
    if not code:
        raise HTTPException(status_code=400, detail="Well Code is required")
    if not name:
        raise HTTPException(status_code=400, detail="Well Name is required")
    if not location:
        raise HTTPException(status_code=400, detail="Well Location is required")
    if not block:
        raise HTTPException(status_code=400, detail="Block is required")
    if not objective:
        raise HTTPException(status_code=400, detail="Objective is required")

    existing = db.scalar(select(Well).where(Well.well_code == code))
    if existing and not existing.is_deleted:
        raise HTTPException(status_code=400, detail=f"Well code '{code}' already exists")
    if existing and existing.is_deleted:
        existing.rig_id = rig_id
        existing.well_name = name
        existing.well_location = location
        existing.block = block
        existing.objective = objective
        existing.remarks = payload.get("remarks")
        existing.is_deleted = False
        existing.deleted_at = None
        existing.updated_by = current_user.id
        db.commit()
        db.refresh(existing)
        log_audit(
            db, user=current_user, action="RESTORE", module=MODULE_WELLS,
            entity_id=existing.id, entity_code=code,
            details=f"Restored existing deleted well {code} on create", request=request,
        )
        return _build_well_out(existing)

    instance = Well(
        rig_id=rig_id,
        well_code=code,
        well_name=name,
        well_location=location,
        block=block,
        objective=objective,
        remarks=payload.get("remarks"),
        created_by=current_user.id,
        updated_by=current_user.id,
    )
    db.add(instance)
    db.commit()
    db.refresh(instance)
    log_audit(
        db, user=current_user, action="CREATE", module=MODULE_WELLS,
        entity_id=instance.id, entity_code=code,
        details=f"Created well {code} - {name}", request=request,
    )
    return _build_well_out(instance)


@router.put("/wells/{record_id}", response_model=WellOut)
def update_well(
    record_id: int,
    payload: dict[str, Any],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> WellOut:
    instance = db.get(Well, record_id)
    if not instance or instance.is_deleted:
        raise HTTPException(status_code=404, detail="Well not found")

    if "rig_id" in payload and payload["rig_id"]:
        try:
            rig_id = int(payload["rig_id"])
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Invalid Rig selection") from exc
        _check_rig_exists(db, rig_id)
        instance.rig_id = rig_id

    new_code = str(payload.get("well_code") or payload.get("code") or "").strip()
    if new_code and new_code != instance.well_code:
        existing = db.scalar(select(Well).where(Well.well_code == new_code))
        if existing and existing.id != record_id:
            raise HTTPException(status_code=400, detail=f"Well code '{new_code}' already exists")
        instance.well_code = new_code

    for field in ("well_name", "name"):
        if payload.get(field):
            instance.well_name = str(payload.get(field)).strip()
    if "well_location" in payload and payload["well_location"] is not None:
        instance.well_location = str(payload["well_location"]).strip()
    if "block" in payload and payload["block"] is not None:
        instance.block = str(payload["block"]).strip()
    if "objective" in payload and payload["objective"] is not None:
        instance.objective = str(payload["objective"]).strip()
    if "remarks" in payload:
        instance.remarks = payload.get("remarks")

    instance.updated_by = current_user.id
    db.commit()
    db.refresh(instance)
    log_audit(
        db, user=current_user, action="UPDATE", module=MODULE_WELLS,
        entity_id=instance.id, entity_code=instance.well_code,
        details=f"Updated well {instance.well_code}", request=request,
    )
    return _build_well_out(instance)


@router.delete("/wells/{record_id}")
def soft_delete_well(
    record_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> dict[str, Any]:
    instance = db.get(Well, record_id)
    if not instance or instance.is_deleted:
        raise HTTPException(status_code=404, detail="Well not found")
    instance.is_deleted = True
    instance.deleted_at = datetime.now(UTC)
    instance.updated_by = current_user.id
    db.commit()
    log_audit(
        db, user=current_user, action="SOFT_DELETE", module=MODULE_WELLS,
        entity_id=instance.id, entity_code=instance.well_code,
        details=f"Soft deleted well {instance.well_code}", request=request,
    )
    return {"status": "success", "message": "Well moved to deleted entries"}


@router.post("/wells/{record_id}/restore")
def restore_well(
    record_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> dict[str, Any]:
    instance = db.get(Well, record_id)
    if not instance or not instance.is_deleted:
        raise HTTPException(status_code=404, detail="Deleted well not found")
    instance.is_deleted = False
    instance.deleted_at = None
    instance.updated_by = current_user.id
    db.commit()
    log_audit(
        db, user=current_user, action="RESTORE", module=MODULE_WELLS,
        entity_id=instance.id, entity_code=instance.well_code,
        details=f"Restored well {instance.well_code}", request=request,
    )
    return {"status": "success", "message": "Well restored"}


@router.delete("/wells/{record_id}/permanent")
def permanent_delete_well(
    record_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> dict[str, Any]:
    instance = db.get(Well, record_id)
    if not instance:
        raise HTTPException(status_code=404, detail="Well not found")
    code = instance.well_code
    db.delete(instance)
    db.commit()
    log_audit(
        db, user=current_user, action="PERMANENT_DELETE", module=MODULE_WELLS,
        entity_id=record_id, entity_code=code,
        details=f"Permanently deleted well {code}", request=request,
    )
    return {"status": "success", "message": "Well permanently deleted"}


@router.get("/wells/import-template")
def download_wells_template(
    db: Annotated[Session, Depends(get_db)],
    current_user: User = Depends(get_current_user),
) -> Response:
    rig_codes = [str(c) for c in db.scalars(
        select(Rig.rig_code).where(Rig.is_deleted == False).order_by(Rig.rig_code)
    ).all()]
    block_values = [str(v) for v in db.scalars(
        select(Well.block).where(Well.is_deleted == False).distinct().order_by(Well.block)
    ).all()]
    return template_xlsx_response(
        "wells_template",
        ["rig_code", "well_code", "well_name", "well_location", "block", "objective", "remarks"],
        sample_rows=[
            ["RIG001", "WELL001", "Exploratory Well 1", "Block 12, Offshore", "Block A", "Appraisal", "Optional remarks"],
            ["RIG001", "WELL002", "Development Well 2", "Block 12, Offshore", "Block B", "Production", ""],
        ],
        dropdowns={1: rig_codes, 5: block_values},
        note="Rigs must already exist — create them in the Rig Management tab first. Codes must be unique.",
    )


@router.post("/wells/import", response_model=BulkImportResponse)
async def import_wells(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request = None,
) -> BulkImportResponse:
    contents = await file.read()
    try:
        rows = read_tabular_file(contents, file.filename or "")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    imported = 0
    errors: list[str] = []
    for r_num, row in rows:
        try:
            rig_ref = str(row_get(row, "rig_code", "rig", "rig_id", "rig_name") or "").strip()
            if not rig_ref:
                raise ValueError("Rig is mandatory")
            rig = None
            try:
                rig = db.get(Rig, int(rig_ref))
            except ValueError:
                rig = None
            if not rig or rig.is_deleted:
                rig = db.scalar(select(Rig).where(Rig.rig_code == rig_ref, Rig.is_deleted == False))
            if not rig:
                raise ValueError(f"Rig '{rig_ref}' not found — create the rig first")

            code = str(row_get(row, "well_code", "code", "wellcode") or "").strip()
            name = str(row_get(row, "well_name", "name", "wellname") or "").strip()
            location = str(row_get(row, "well_location", "location") or "").strip()
            block = str(row_get(row, "block") or "").strip()
            objective = str(row_get(row, "objective") or "").strip()
            remarks = row_get(row, "remarks", "remark")
            if not code:
                raise ValueError("Missing well_code")
            if not name:
                raise ValueError("Missing well_name")
            if not location:
                raise ValueError("Missing well_location")
            if not block:
                raise ValueError("Missing block")
            if not objective:
                raise ValueError("Missing objective")

            existing = db.scalar(select(Well).where(Well.well_code == code))
            if existing:
                existing.rig_id = rig.id
                existing.well_name = name
                existing.well_location = location
                existing.block = block
                existing.objective = objective
                if remarks:
                    existing.remarks = str(remarks)
                existing.is_deleted = False
                existing.deleted_at = None
                existing.updated_by = current_user.id
                imported += 1
            else:
                db.add(Well(
                    rig_id=rig.id, well_code=code, well_name=name, well_location=location,
                    block=block, objective=objective, remarks=str(remarks) if remarks else None,
                    created_by=current_user.id, updated_by=current_user.id,
                ))
                imported += 1
        except Exception as exc:
            errors.append(f"Row {r_num}: {exc}")
    db.commit()
    log_audit(
        db, user=current_user, action="BULK_IMPORT", module=MODULE_WELLS,
        details=f"Imported {imported} wells with {len(errors)} errors from {file.filename}", request=request,
    )
    return BulkImportResponse(imported_count=imported, error_count=len(errors), errors=errors[:30], success=not errors)


@router.get("/wells/export")
def export_wells(
    format: str = Query("xlsx", pattern="^(xlsx|csv)$"),
    include_deleted: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request = None,
) -> Response:
    stmt = select(Well)
    if not include_deleted:
        stmt = stmt.where(Well.is_deleted == False)
    records = db.scalars(stmt).all()
    log_audit(
        db, user=current_user, action="EXPORT", module=MODULE_WELLS,
        details=f"Exported {len(records)} wells as {format}", request=request,
    )
    headers = [
        "rig_code", "rig_name", "well_code", "well_name", "well_location", "block",
        "objective", "remarks", "status", "config_status", "depth_unit",
        "total_depth", "total_days", "is_deleted", "created_at",
    ]
    data: list[list[Any]] = []
    for w in records:
        total_depth, total_days = _well_totals(w)
        data.append([
            w.rig.rig_code if w.rig else "",
            w.rig.rig_name if w.rig else "",
            w.well_code, w.well_name, w.well_location, w.block, w.objective,
            w.remarks or "", w.status, w.config_status, w.depth_unit,
            str(total_depth) if total_depth is not None else "",
            str(total_days), w.is_deleted,
            w.created_at.isoformat() if w.created_at else "",
        ])
    return _spreadsheet(data, headers, "wells", format)


# ---------------------------------------------------------------------------
# Well configuration
# ---------------------------------------------------------------------------


@router.get("/wells/{record_id}/configuration", response_model=WellConfigurationOut)
def get_well_configuration(
    record_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> WellConfigurationOut:
    well = db.get(Well, record_id)
    if not well or well.is_deleted:
        raise HTTPException(status_code=404, detail="Well not found")
    return _build_config_out(well)


@router.put("/wells/{record_id}/configuration", response_model=WellConfigurationOut)
def save_well_configuration(
    record_id: int,
    payload: WellConfigurationIn,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> WellConfigurationOut:
    well = db.get(Well, record_id)
    if not well or well.is_deleted:
        raise HTTPException(status_code=404, detail="Well not found")
    _ensure_well_editable(well)

    if payload.depth_unit not in DEPTH_UNITS:
        raise HTTPException(status_code=400, detail="Depth unit must be 'm' (metre) or 'ft' (feet)")

    if not payload.sections:
        raise HTTPException(status_code=400, detail="Add at least one section before saving")

    # Validate sections and phases up front so a bad payload never half-writes.
    seen_section_ids: set[int] = set()
    prev_to_depth: Decimal | None = None
    for i, sec in enumerate(payload.sections):
        section = db.get(HoleSection, sec.section_id)
        if not section or section.is_deleted:
            raise HTTPException(status_code=400, detail=f"Section #{i + 1}: selected hole section no longer exists")
        if sec.section_id in seen_section_ids:
            raise HTTPException(status_code=400, detail=f"Section '{section.section_code}' is duplicated")
        seen_section_ids.add(sec.section_id)
        if sec.from_depth > sec.to_depth:
            raise HTTPException(
                status_code=400,
                detail=f"Section '{section.section_code}': from depth cannot exceed to depth",
            )
        if prev_to_depth is not None and sec.from_depth < prev_to_depth:
            raise HTTPException(
                status_code=400,
                detail=f"Section '{section.section_code}': from depth must not be less than the previous section's to depth ({prev_to_depth})",
            )
        prev_to_depth = sec.to_depth
        seen_phase_ids: set[int] = set()
        for j, ph in enumerate(sec.phases):
            phase = db.get(Phase, ph.phase_id)
            if not phase or phase.is_deleted:
                raise HTTPException(status_code=400, detail=f"Section '{section.section_code}' phase #{j + 1}: phase no longer exists")
            if ph.phase_id in seen_phase_ids:
                raise HTTPException(status_code=400, detail=f"Section '{section.section_code}': phase '{phase.phase_code}' is duplicated")
            seen_phase_ids.add(ph.phase_id)
            if ph.days < 0:
                raise HTTPException(status_code=400, detail=f"Section '{section.section_code}': phase days cannot be negative")

    # Replace configuration wholesale. The old sections are deleted through the
    # ORM (never a bulk ``Query.delete()``) so the ``WellSection.phases``
    # cascade runs: a bulk DELETE skips cascades, which makes PostgreSQL reject
    # the section DELETE with a foreign-key violation on
    # ``fk_well_phases_section_id_well_sections`` — surfaced to the user as a
    # 409 "conflicts with existing records" — and leaves the phases behind as
    # orphans that are then double-counted in the totals.
    for existing_section in list(well.sections):
        db.delete(existing_section)
    db.flush()
    well.depth_unit = payload.depth_unit
    for i, sec in enumerate(payload.sections):
        section_row = WellSection(
            well_id=well.id,
            section_id=sec.section_id,
            from_depth=sec.from_depth,
            to_depth=sec.to_depth,
            remarks=sec.remarks,
            sort_order=i,
            created_by=current_user.id,
            updated_by=current_user.id,
        )
        db.add(section_row)
        db.flush()
        for j, ph in enumerate(sec.phases):
            db.add(WellPhase(
                section_id=section_row.id,
                phase_id=ph.phase_id,
                days=ph.days,
                remarks=ph.remarks,
                sort_order=j,
                created_by=current_user.id,
                updated_by=current_user.id,
            ))

    well.updated_by = current_user.id
    db.commit()
    db.refresh(well)
    # Reload the section collection so the response is built from the rows just
    # written rather than from state this session may still be holding.
    db.expire(well, ["sections"])
    log_audit(
        db, user=current_user, action="UPDATE", module=MODULE_CONFIG,
        entity_id=well.id, entity_code=well.well_code,
        details=f"Saved configuration for well {well.well_code} ({len(payload.sections)} section(s))",
        request=request,
    )
    return _build_config_out(well)


@router.post("/wells/{record_id}/mark", response_model=WellOut)
def mark_well(
    record_id: int,
    payload: MarkWellIn,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> WellOut:
    well = db.get(Well, record_id)
    if not well or well.is_deleted:
        raise HTTPException(status_code=404, detail="Well not found")

    action = payload.action
    remarks = (payload.remarks or "").strip()

    if action == "configure":
        if well.status == "completed":
            raise HTTPException(status_code=400, detail="A completed well cannot be configured — mark it Active first.")
        if not remarks:
            raise HTTPException(status_code=400, detail="Remarks are required when marking a well as configured.")
        well.config_status = "configured"
        detail = f"Marked well {well.well_code} as configured"
    elif action == "draft":
        if well.status == "completed":
            raise HTTPException(status_code=400, detail="A completed well cannot be marked as draft — mark it Active first.")
        if not remarks:
            raise HTTPException(status_code=400, detail="Remarks are required when marking a configured well back to draft.")
        well.config_status = "draft"
        detail = f"Marked well {well.well_code} as draft"
    elif action == "complete":
        if well.status == "completed":
            raise HTTPException(status_code=400, detail="Well is already completed.")
        if not remarks:
            raise HTTPException(status_code=400, detail="Remarks are required when marking a well as completed.")
        well.status = "completed"
        detail = f"Marked well {well.well_code} as completed"
    elif action == "activate":
        if well.status == "active":
            raise HTTPException(status_code=400, detail="Well is already active.")
        if not remarks:
            raise HTTPException(status_code=400, detail="Remarks are required when marking a well back to active.")
        well.status = "active"
        detail = f"Marked well {well.well_code} as active"
    else:  # pragma: no cover - guarded by Literal type
        raise HTTPException(status_code=400, detail=f"Unknown action '{action}'")

    if remarks:
        detail += f" — remarks: {remarks}"

    well.updated_by = current_user.id
    db.commit()
    db.refresh(well)
    log_audit(
        db, user=current_user, action="UPDATE", module=MODULE_CONFIG,
        entity_id=well.id, entity_code=well.well_code, details=detail, request=request,
    )
    return _build_well_out(well)
