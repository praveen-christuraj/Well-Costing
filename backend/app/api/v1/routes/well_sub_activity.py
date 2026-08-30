"""Well Sub Activities API routes.

The page is **completely well scoped**: every read and every bulk operation
takes a ``well_id`` context (the user picks the rig and the corresponding well
before any data entry), and ``sub_activity_code`` uniqueness is enforced
*within that well* — the same code may exist on a different well.

Carries the common template: Import (XLSX/CSV) into the selected well,
XLSX/CSV export, print-ready data, soft delete → deleted-entries tab →
restore / permanent delete, audit logging and duplicate-code prevention.
The Activity column always resolves against the Master Data ``activities``
list, so the Master Data page controls what a sub activity can belong to.

Path ordering note: static paths (``/deleted``, ``/export``,
``/import``, ``/import-template``) are declared before the ``/{record_id}``
routes so FastAPI matches them first.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportArgumentType=false, reportOptionalMemberAccess=false, reportUnknownParameterType=false, reportMissingTypeArgument=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false, reportOptionalIterable=false

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db
from app.models.master_data import Activity
from app.models.rig_well import Well
from app.models.user import User
from app.models.well_sub_activity import WellSubActivity
from app.schemas.master_data import BulkImportResponse
from app.schemas.well_sub_activity import (
    WellSubActivityIn,
    WellSubActivityOut,
    WellSubActivityUpdate,
)
from app.services.audit import log_audit
from app.services.import_helpers import (
    read_tabular_file,
    row_get,
    spreadsheet_response,
    template_xlsx_response,
)

router = APIRouter(prefix="/well-sub-activities", tags=["well-sub-activities"])

MODULE = "Well Sub Activities"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _check_well_exists(db: Session, well_id: int) -> Well:
    well = db.get(Well, well_id)
    if not well or well.is_deleted:
        raise HTTPException(status_code=404, detail="Well not found or deleted")
    return well


def _check_activity_exists(db: Session, activity_id: int) -> Activity:
    activity = db.get(Activity, activity_id)
    if not activity or activity.is_deleted:
        raise HTTPException(
            status_code=400,
            detail="Selected Activity not found — pick an Activity defined on the Master Data page",
        )
    return activity


def _resolve_activity(db: Session, ref: Any) -> Activity:
    """Resolve an Activity by id, code (exact then case-insensitive) or fuzzy name."""

    text = str(ref or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Activity is required")
    try:
        activity = db.get(Activity, int(text))
        if activity and not activity.is_deleted:
            return activity
    except (TypeError, ValueError):
        pass
    activity = db.scalar(select(Activity).where(Activity.activity_code == text, Activity.is_deleted == False))
    if activity:
        return activity
    activity = db.scalar(select(Activity).where(Activity.activity_code.ilike(text), Activity.is_deleted == False))
    if activity:
        return activity
    activity = db.scalar(
        select(Activity).where(Activity.activity_name.ilike(f"%{text}%"), Activity.is_deleted == False)
    )
    if activity:
        return activity
    raise HTTPException(
        status_code=400,
        detail=f"Activity '{text}' not found — define it on the Master Data page first",
    )


def _get_record(db: Session, record_id: int) -> WellSubActivity:
    record = db.get(WellSubActivity, record_id)
    if not record or record.is_deleted:
        raise HTTPException(status_code=404, detail="Sub activity not found")
    return record


def _build_out(record: WellSubActivity) -> WellSubActivityOut:
    well = record.well
    activity = record.activity
    activity_code = activity.activity_code if activity else None
    activity_name = activity.activity_name if activity else None
    return WellSubActivityOut(
        id=record.id,
        well_id=record.well_id,
        sub_activity_code=record.sub_activity_code or "",
        sub_activity_name=record.sub_activity_name or "",
        activity_id=record.activity_id,
        responsible_party=record.responsible_party or "",
        description=record.description or "",
        is_deleted=record.is_deleted,
        deleted_at=record.deleted_at,
        created_at=record.created_at,
        updated_at=record.updated_at,
        well_code=well.well_code if well else None,
        well_name=well.well_name if well else None,
        rig_id=well.rig_id if well else None,
        rig_code=well.rig.rig_code if well and well.rig else None,
        rig_name=well.rig.rig_name if well and well.rig else None,
        activity_code=activity_code,
        activity_name=activity_name,
        activity_display=(
            f"{activity_code} - {activity_name}"
            if activity_code and activity_name
            else (activity_code or activity_name)
        ),
    )


def _code_in_use(
    db: Session, well_id: int, code: str, *, exclude_id: int | None = None
) -> WellSubActivity | None:
    """Duplicate check — codes must never repeat *within the same well*."""

    stmt = select(WellSubActivity).where(
        WellSubActivity.well_id == well_id,
        WellSubActivity.sub_activity_code == code,
        WellSubActivity.is_deleted == False,
    )
    if exclude_id is not None:
        stmt = stmt.where(WellSubActivity.id != exclude_id)
    return db.scalar(stmt)


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


@router.get("", response_model=list[WellSubActivityOut])
def list_sub_activities(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    well_id: int,
    search: str | None = None,
) -> list[WellSubActivityOut]:
    """Active sub activities of one well (the page's well context)."""

    _check_well_exists(db, well_id)
    stmt = (
        select(WellSubActivity)
        .where(WellSubActivity.well_id == well_id, WellSubActivity.is_deleted == False)
        .order_by(WellSubActivity.id.desc())
    )
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            or_(
                WellSubActivity.sub_activity_code.ilike(like),
                WellSubActivity.sub_activity_name.ilike(like),
                WellSubActivity.responsible_party.ilike(like),
                WellSubActivity.description.ilike(like),
            )
        )
    return [_build_out(record) for record in db.scalars(stmt).all()]


@router.get("/deleted", response_model=list[WellSubActivityOut])
def list_sub_activities_deleted(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    well_id: int,
) -> list[WellSubActivityOut]:
    """Soft-deleted sub activities of one well (the Deleted Entries tab)."""

    _check_well_exists(db, well_id)
    stmt = (
        select(WellSubActivity)
        .where(WellSubActivity.well_id == well_id, WellSubActivity.is_deleted == True)
        .order_by(WellSubActivity.deleted_at.desc())
    )
    return [_build_out(record) for record in db.scalars(stmt).all()]


# ---------------------------------------------------------------------------
# Import / export
# ---------------------------------------------------------------------------


@router.get("/import-template")
def download_import_template(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    activity_codes = [str(c) for c in db.scalars(
        select(Activity.activity_code).where(Activity.is_deleted == False).order_by(Activity.activity_code)
    ).all()]
    return template_xlsx_response(
        "well_sub_activities_template",
        ["sub_activity_code", "sub_activity_name", "activity", "responsible_party", "description"],
        sample_rows=[
            ["RIH-01", "Run in hole with tubing", "DRL", "Schlumberger", "RIH with completion tubing string"],
            ["TEST-01", "Well testing", "TST", "Halliburton", "Flow and shut-in test of the well"],
        ],
        dropdowns={3: activity_codes},
        note=(
            "Rows import into the well currently selected on the page. "
            "The 'activity' column accepts an Activity code or name from Master Data; "
            "sub_activity_code must be unique within the well. All columns are mandatory."
        ),
    )


@router.post("/import", response_model=BulkImportResponse)
async def import_sub_activities(
    well_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request = None,
) -> BulkImportResponse:
    """Bulk-import sub activities into the selected well (upsert per well+code)."""

    well = _check_well_exists(db, well_id)
    contents = await file.read()
    try:
        rows = read_tabular_file(contents, file.filename or "")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    imported = 0
    errors: list[str] = []
    seen_codes: set[str] = set()
    for r_num, row in rows:
        try:
            code = str(row_get(row, "sub_activity_code", "code", "sub_activity") or "").strip()
            name = str(row_get(row, "sub_activity_name", "name") or "").strip()
            responsible = str(row_get(row, "responsible_party", "responsible", "company") or "").strip()
            description = str(row_get(row, "description", "remarks", "remark") or "").strip()
            if not code:
                raise ValueError("Missing sub_activity_code")
            if code.lower() in seen_codes:
                raise ValueError(f"sub_activity_code '{code}' is duplicated inside the file")
            seen_codes.add(code.lower())
            activity_ref = row_get(row, "activity", "activity_code", "activity_name")
            if activity_ref is None:
                raise ValueError("Missing activity")
            activity = _resolve_activity(db, activity_ref)
            if not name:
                raise ValueError("Missing sub_activity_name")
            if not responsible:
                raise ValueError("Missing responsible_party")
            if not description:
                raise ValueError("Missing description")

            existing = db.scalar(
                select(WellSubActivity).where(
                    WellSubActivity.well_id == well.id,
                    WellSubActivity.sub_activity_code == code,
                )
            )
            if existing and not existing.is_deleted:
                existing.sub_activity_name = name
                existing.activity_id = activity.id
                existing.responsible_party = responsible
                existing.description = description
                existing.updated_by = current_user.id
                imported += 1
            elif existing:
                existing.sub_activity_name = name
                existing.activity_id = activity.id
                existing.responsible_party = responsible
                existing.description = description
                existing.is_deleted = False
                existing.deleted_at = None
                existing.updated_by = current_user.id
                imported += 1
            else:
                db.add(WellSubActivity(
                    well_id=well.id,
                    sub_activity_code=code,
                    sub_activity_name=name,
                    activity_id=activity.id,
                    responsible_party=responsible,
                    description=description,
                    created_by=current_user.id,
                    updated_by=current_user.id,
                ))
                imported += 1
        except HTTPException as exc:
            errors.append(f"Row {r_num}: {exc.detail}")
        except Exception as exc:
            errors.append(f"Row {r_num}: {exc}")
    db.commit()
    log_audit(
        db, user=current_user, action="BULK_IMPORT", module=MODULE,
        details=f"Imported {imported} sub activities into well {well.well_code} "
                f"with {len(errors)} errors from {file.filename}",
        request=request,
    )
    return BulkImportResponse(imported_count=imported, error_count=len(errors), errors=errors[:30], success=not errors)


@router.get("/export")
def export_sub_activities(
    format: str = Query("xlsx", pattern="^(xlsx|csv)$"),
    well_id: int | None = None,
    include_deleted: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request = None,
) -> Response:
    stmt = select(WellSubActivity)
    if well_id is not None:
        stmt = stmt.where(WellSubActivity.well_id == well_id)
    if not include_deleted:
        stmt = stmt.where(WellSubActivity.is_deleted == False)
    records = db.scalars(stmt.order_by(WellSubActivity.id.desc())).all()
    scope = ""
    if well_id is not None:
        well = db.get(Well, well_id)
        scope = f" of well {well.well_code if well else well_id}"
    log_audit(
        db, user=current_user, action="EXPORT", module=MODULE,
        details=f"Exported {len(records)} sub activities{scope} as {format}", request=request,
    )
    headers = [
        "rig_code", "well_code", "well_name", "sub_activity_code", "sub_activity_name",
        "activity_code", "activity_name", "responsible_party", "description",
        "is_deleted", "created_at",
    ]
    data = []
    for record in records:
        out = _build_out(record)
        data.append([
            out.rig_code or "", out.well_code or "", out.well_name or "",
            out.sub_activity_code, out.sub_activity_name,
            out.activity_code or "", out.activity_name or "",
            out.responsible_party, out.description,
            record.is_deleted,
            record.created_at.isoformat() if record.created_at else "",
        ])
    return spreadsheet_response(data, headers, "well_sub_activities", format)


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


@router.get("/{record_id}", response_model=WellSubActivityOut)
def get_sub_activity(
    record_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> WellSubActivityOut:
    return _build_out(_get_record(db, record_id))


@router.post("", response_model=WellSubActivityOut)
def create_sub_activity(
    payload: WellSubActivityIn,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> WellSubActivityOut:
    well = _check_well_exists(db, payload.well_id)
    activity = _check_activity_exists(db, payload.activity_id)

    code = payload.sub_activity_code.strip()
    name = payload.sub_activity_name.strip()
    responsible = payload.responsible_party.strip()
    description = payload.description.strip()
    if not code:
        raise HTTPException(status_code=400, detail="Sub Activity Code is required")
    if not name:
        raise HTTPException(status_code=400, detail="Sub Activity Name is required")
    if not responsible:
        raise HTTPException(status_code=400, detail="Responsible Party/Company is required")
    if not description:
        raise HTTPException(status_code=400, detail="Description/Remarks is required")

    if _code_in_use(db, well.id, code):
        raise HTTPException(
            status_code=400,
            detail=f"Sub activity code '{code}' already exists for this well",
        )

    # Re-creating a soft-deleted code restores that row instead of failing on
    # the unique index — the same behaviour the other entry pages have.
    existing = db.scalar(
        select(WellSubActivity).where(
            WellSubActivity.well_id == well.id,
            WellSubActivity.sub_activity_code == code,
        )
    )
    if existing and existing.is_deleted:
        existing.sub_activity_name = name
        existing.activity_id = activity.id
        existing.responsible_party = responsible
        existing.description = description
        existing.is_deleted = False
        existing.deleted_at = None
        existing.updated_by = current_user.id
        db.commit()
        db.refresh(existing)
        log_audit(
            db, user=current_user, action="RESTORE", module=MODULE,
            entity_id=existing.id, entity_code=code,
            details=f"Restored deleted sub activity {code} of well {well.well_code} on create",
            request=request,
        )
        return _build_out(existing)

    record = WellSubActivity(
        well_id=well.id,
        sub_activity_code=code,
        sub_activity_name=name,
        activity_id=activity.id,
        responsible_party=responsible,
        description=description,
        created_by=current_user.id,
        updated_by=current_user.id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    log_audit(
        db, user=current_user, action="CREATE", module=MODULE,
        entity_id=record.id, entity_code=code,
        details=f"Created sub activity {code} - {name} for well {well.well_code} "
                f"(party: {responsible})",
        request=request,
    )
    return _build_out(record)


@router.put("/{record_id}", response_model=WellSubActivityOut)
def update_sub_activity(
    record_id: int,
    payload: WellSubActivityUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> WellSubActivityOut:
    record = _get_record(db, record_id)

    if payload.sub_activity_code and payload.sub_activity_code.strip() != record.sub_activity_code:
        new_code = payload.sub_activity_code.strip()
        clash = db.scalar(
            select(WellSubActivity).where(
                WellSubActivity.well_id == record.well_id,
                WellSubActivity.sub_activity_code == new_code,
                WellSubActivity.id != record.id,
            )
        )
        if clash and not clash.is_deleted:
            raise HTTPException(
                status_code=400,
                detail=f"Sub activity code '{new_code}' already exists for this well",
            )
        if clash:
            raise HTTPException(
                status_code=400,
                detail=f"Sub activity code '{new_code}' sits in this well's deleted entries — "
                       "restore it or delete it permanently first.",
            )
        record.sub_activity_code = new_code
    if payload.sub_activity_name is not None:
        if not payload.sub_activity_name.strip():
            raise HTTPException(status_code=400, detail="Sub Activity Name is required")
        record.sub_activity_name = payload.sub_activity_name.strip()
    if payload.activity_id is not None:
        record.activity_id = _check_activity_exists(db, payload.activity_id).id
    if payload.responsible_party is not None:
        if not payload.responsible_party.strip():
            raise HTTPException(status_code=400, detail="Responsible Party/Company is required")
        record.responsible_party = payload.responsible_party.strip()
    if payload.description is not None:
        if not payload.description.strip():
            raise HTTPException(status_code=400, detail="Description/Remarks is required")
        record.description = payload.description.strip()

    record.updated_by = current_user.id
    db.commit()
    db.refresh(record)
    log_audit(
        db, user=current_user, action="UPDATE", module=MODULE,
        entity_id=record.id, entity_code=record.sub_activity_code,
        details=f"Updated sub activity {record.sub_activity_code} of well "
                f"{record.well.well_code if record.well else record.well_id}",
        request=request,
    )
    return _build_out(record)


@router.delete("/{record_id}")
def soft_delete_sub_activity(
    record_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> dict[str, Any]:
    record = _get_record(db, record_id)
    record.is_deleted = True
    record.deleted_at = datetime.now(UTC)
    record.updated_by = current_user.id
    db.commit()
    log_audit(
        db, user=current_user, action="SOFT_DELETE", module=MODULE,
        entity_id=record.id, entity_code=record.sub_activity_code,
        details=f"Soft deleted sub activity {record.sub_activity_code} of well "
                f"{record.well.well_code if record.well else record.well_id}",
        request=request,
    )
    return {"status": "success", "message": "Sub activity moved to deleted entries"}


@router.post("/{record_id}/restore")
def restore_sub_activity(
    record_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> dict[str, Any]:
    record = db.get(WellSubActivity, record_id)
    if not record or not record.is_deleted:
        raise HTTPException(status_code=404, detail="Deleted sub activity not found")
    if _code_in_use(db, record.well_id, record.sub_activity_code, exclude_id=record.id):
        raise HTTPException(
            status_code=400,
            detail=f"Sub activity code '{record.sub_activity_code}' is already in use on this well — "
                   "rename the active entry first.",
        )
    record.is_deleted = False
    record.deleted_at = None
    record.updated_by = current_user.id
    db.commit()
    log_audit(
        db, user=current_user, action="RESTORE", module=MODULE,
        entity_id=record.id, entity_code=record.sub_activity_code,
        details=f"Restored sub activity {record.sub_activity_code} of well "
                f"{record.well.well_code if record.well else record.well_id}",
        request=request,
    )
    return {"status": "success", "message": "Sub activity restored"}


@router.delete("/{record_id}/permanent")
def permanent_delete_sub_activity(
    record_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> dict[str, Any]:
    record = db.get(WellSubActivity, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Sub activity not found")
    code = record.sub_activity_code
    db.delete(record)
    db.commit()
    log_audit(
        db, user=current_user, action="PERMANENT_DELETE", module=MODULE,
        entity_id=record_id, entity_code=code,
        details=f"Permanently deleted sub activity {code}",
        request=request,
    )
    return {"status": "success", "message": "Sub activity permanently deleted"}
