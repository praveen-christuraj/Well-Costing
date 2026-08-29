"""AFE Management API routes.

Two tabs, one backbone:

* **AFE** — create the well-scoped AFE header (rig → well → code/name/type) with
  the common template: Import (XLSX/CSV), XLSX/CSV export, print-ready data,
  soft delete → deleted-entries → restore/permanent delete, audit logging and
  duplicate-code prevention.
* **AFE Cost Estimation** — configure Services / Consumables / Tangibles for one
  AFE, price them with :mod:`app.domain.afe_costing`, move the AFE through
  draft → submitted → approved and print or export the compiled estimate.

Path ordering note: static paths (``/afes/dropdown``, ``/afes/export``,
``/afes/import-template``, ``/estimates/export``) are declared before the
``/{record_id}`` routes so FastAPI matches them first.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportArgumentType=false, reportOptionalMemberAccess=false, reportUnknownParameterType=false, reportMissingTypeArgument=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false, reportOptionalIterable=false

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db
from app.models.afe import Afe
from app.models.rig_well import Rig, Well
from app.models.user import User
from app.schemas.afe import (
    AfeDropdownOut,
    AfeEstimateOut,
    AfeIn,
    AfeOut,
    AfeStatusIn,
    AfeUpdate,
    EstimateIn,
)
from app.schemas.master_data import BulkImportResponse
from app.services import afe_estimation
from app.services.afe_estimation import AfeValidationError
from app.services.audit import log_audit
from app.services.import_helpers import (
    read_tabular_file,
    row_get,
    spreadsheet_response,
    template_xlsx_response,
)

router = APIRouter(prefix="/afe", tags=["afe"])

MODULE_AFE = "AFE"
MODULE_ESTIMATE = "AFE Cost Estimation"
AFE_TYPES = ("Drilling", "Completion")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_afe(db: Session, afe_id: int) -> Afe:
    afe = db.get(Afe, afe_id)
    if not afe or afe.is_deleted:
        raise HTTPException(status_code=404, detail="AFE not found")
    return afe


def _normalize_type(value: Any) -> str:
    """Accept the usual spellings of the two AFE types."""

    text = str(value or "").strip().lower()
    if text in {"drilling", "drill", "drl", "d"}:
        return "Drilling"
    if text in {"completion", "completions", "comp", "cmpl", "c"}:
        return "Completion"
    raise AfeValidationError("AFE Type must be 'Drilling' or 'Completion'")


def _resolve_rig(db: Session, ref: Any) -> Rig:
    """Resolve a rig by id, code (exact then case-insensitive) or fuzzy name."""

    text = str(ref or "").strip()
    if not text:
        raise AfeValidationError("Rig is required")
    try:
        rig = db.get(Rig, int(text))
        if rig and not rig.is_deleted:
            return rig
    except (TypeError, ValueError):
        pass
    rig = db.scalar(select(Rig).where(Rig.rig_code == text, Rig.is_deleted == False))
    if rig:
        return rig
    rig = db.scalar(select(Rig).where(Rig.rig_code.ilike(text), Rig.is_deleted == False))
    if rig:
        return rig
    rig = db.scalar(select(Rig).where(Rig.rig_name.ilike(f"%{text}%"), Rig.is_deleted == False))
    if rig:
        return rig
    raise AfeValidationError(f"Rig '{text}' not found — create it in Rig & Well Management first")


def _resolve_well(db: Session, ref: Any, rig_id: int) -> Well:
    """Resolve a well that belongs to the given rig."""

    text = str(ref or "").strip()
    if not text:
        raise AfeValidationError("Well is required")
    stmt = select(Well).where(Well.rig_id == rig_id, Well.is_deleted == False)
    try:
        well = db.get(Well, int(text))
        if well and not well.is_deleted and well.rig_id == rig_id:
            return well
    except (TypeError, ValueError):
        pass
    well = db.scalar(stmt.where(Well.well_code == text))
    if well:
        return well
    well = db.scalar(stmt.where(Well.well_code.ilike(text)))
    if well:
        return well
    well = db.scalar(stmt.where(Well.well_name.ilike(f"%{text}%")))
    if well:
        return well
    raise AfeValidationError(f"Well '{text}' not found under the selected rig")


def _list_afes(db: Session, *, deleted: bool = False, search: str | None = None) -> list[Afe]:
    stmt = select(Afe).where(Afe.is_deleted == deleted)
    stmt = stmt.order_by(Afe.deleted_at.desc() if deleted else Afe.id.desc())
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(Afe.afe_code.ilike(like), Afe.afe_name.ilike(like), Afe.remarks.ilike(like)))
    return list(db.scalars(stmt).all())


# ---------------------------------------------------------------------------
# AFE tab — reads
# ---------------------------------------------------------------------------


@router.get("/afes/dropdown", response_model=list[AfeDropdownOut])
def list_afes_dropdown(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[AfeDropdownOut]:
    records = db.scalars(select(Afe).where(Afe.is_deleted == False).order_by(Afe.id.desc())).all()
    return [
        AfeDropdownOut(
            id=afe.id,
            afe_code=afe.afe_code,
            afe_name=afe.afe_name,
            display_name=f"{afe.afe_code} - {afe.afe_name}",
        )
        for afe in records
    ]


@router.get("/afes/deleted", response_model=list[AfeOut])
def list_afes_deleted(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[AfeOut]:
    return [afe_estimation.build_afe_out(afe) for afe in _list_afes(db, deleted=True)]


@router.get("/afes", response_model=list[AfeOut])
def list_afes(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    search: str | None = None,
) -> list[AfeOut]:
    return [afe_estimation.build_afe_out(afe) for afe in _list_afes(db, search=search)]


# ---------------------------------------------------------------------------
# AFE tab — import / export
# ---------------------------------------------------------------------------


@router.get("/afes/import-template")
def download_afes_template(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    rigs = db.scalars(select(Rig).where(Rig.is_deleted == False).order_by(Rig.rig_code)).all()
    wells = db.scalars(select(Well).where(Well.is_deleted == False).order_by(Well.well_code)).all()
    return template_xlsx_response(
        "afe_template",
        ["rig_code", "well_code", "afe_code", "afe_name", "afe_type", "remarks"],
        sample_rows=[
            ["RIG001", "WELL001", "AFE-2026-001", "Surface section drilling", "Drilling", "First AFE"],
            ["RIG001", "WELL001", "AFE-2026-002", "Completion of WELL001", "Completion", ""],
        ],
        dropdowns={1: [rig.rig_code for rig in rigs], 2: [well.well_code for well in wells], 5: list(AFE_TYPES)},
        note=(
            "rig_code and well_code accept a code or a name; the well must belong to that rig. "
            "afe_code must be unique. Dates are not part of this template."
        ),
    )


@router.post("/afes/import", response_model=BulkImportResponse)
async def import_afes(
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
    seen_codes: set[str] = set()
    for r_num, row in rows:
        code = str(row_get(row, "afe_code", "code", "afecode") or "").strip()
        name = str(row_get(row, "afe_name", "name", "afename") or "").strip()
        if not code:
            errors.append(f"Row {r_num}: Missing afe_code")
            continue
        if code.lower() in seen_codes:
            errors.append(f"Row {r_num}: afe_code '{code}' is duplicated inside the file")
            continue
        seen_codes.add(code.lower())
        try:
            rig = _resolve_rig(db, row_get(row, "rig_code", "rig", "rig_name"))
            well = _resolve_well(db, row_get(row, "well_code", "well", "well_name"), rig.id)
            afe_type = _normalize_type(row_get(row, "afe_type", "type") or "Drilling")
        except AfeValidationError as exc:
            errors.append(f"Row {r_num} ({code}): {exc}")
            continue
        if not name:
            name = code
        remarks = row_get(row, "remarks", "remark")
        existing = db.scalar(select(Afe).where(Afe.afe_code == code))
        if existing and not existing.is_deleted:
            errors.append(f"Row {r_num}: afe_code '{code}' already exists")
            continue
        if existing:
            existing.afe_name = name
            existing.afe_type = afe_type
            existing.rig_id = rig.id
            existing.well_id = well.id
            existing.status = "draft"
            existing.is_deleted = False
            existing.deleted_at = None
            existing.updated_by = current_user.id
            imported += 1
            continue
        db.add(Afe(
            afe_code=code,
            afe_name=name,
            afe_type=afe_type,
            rig_id=rig.id,
            well_id=well.id,
            remarks=str(remarks) if remarks else None,
            status="draft",
            created_by=current_user.id,
            updated_by=current_user.id,
        ))
        imported += 1
    db.commit()
    log_audit(
        db, user=current_user, action="BULK_IMPORT", module=MODULE_AFE,
        details=f"Imported {imported} AFEs with {len(errors)} errors from {file.filename}", request=request,
    )
    return BulkImportResponse(
        imported_count=imported, error_count=len(errors), errors=errors[:30], success=not errors
    )


def _afe_export_headers() -> list[str]:
    return [
        "afe_code", "afe_name", "afe_type", "rig_code", "rig_name", "well_code", "well_name",
        "status", "service_count", "consumable_count", "tangible_count", "estimated_total",
        "remarks", "is_deleted", "created_at",
    ]


def _afe_export_rows(afes: list[Afe]) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for afe in afes:
        out = afe_estimation.build_afe_out(afe)
        rows.append([
            out.afe_code, out.afe_name, out.afe_type,
            afe.rig.rig_code if afe.rig else "", afe.rig.rig_name if afe.rig else "",
            afe.well.well_code if afe.well else "", afe.well.well_name if afe.well else "",
            out.status, out.service_count, out.consumable_count, out.tangible_count,
            str(out.estimated_total), afe.remarks or "", afe.is_deleted,
            afe.created_at.isoformat() if afe.created_at else "",
        ])
    return rows


@router.get("/afes/export")
def export_afes(
    format: str = Query("xlsx", pattern="^(xlsx|csv)$"),
    include_deleted: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request = None,
) -> Response:
    afes = _list_afes(db, deleted=include_deleted)
    log_audit(
        db, user=current_user, action="EXPORT", module=MODULE_AFE,
        details=f"Exported {len(afes)} AFEs as {format}", request=request,
    )
    return spreadsheet_response(_afe_export_rows(afes), _afe_export_headers(), "afe_list", format)


@router.get("/afes/{record_id}", response_model=AfeOut)
def get_afe(
    record_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AfeOut:
    return afe_estimation.build_afe_out(_get_afe(db, record_id))


# ---------------------------------------------------------------------------
# AFE tab — writes
# ---------------------------------------------------------------------------


@router.post("/afes", response_model=AfeOut)
def create_afe(
    payload: AfeIn,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> AfeOut:
    code = payload.afe_code.strip()
    if not code:
        raise HTTPException(status_code=400, detail="AFE Code is required")
    if not payload.afe_name.strip():
        raise HTTPException(status_code=400, detail="AFE Name is required")

    existing = db.scalar(select(Afe).where(Afe.afe_code == code))
    if existing and not existing.is_deleted:
        raise HTTPException(status_code=400, detail=f"AFE code '{code}' already exists")

    try:
        rig = _resolve_rig(db, payload.rig_id)
        well = _resolve_well(db, payload.well_id, rig.id)
    except AfeValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Re-creating a soft-deleted code restores that AFE instead of failing on
    # the unique index — the same behaviour the other entry pages have.
    if existing and existing.is_deleted:
        existing.afe_name = payload.afe_name.strip()
        existing.afe_type = payload.afe_type
        existing.rig_id = rig.id
        existing.well_id = well.id
        existing.remarks = payload.remarks
        existing.status = "draft"
        existing.status_remarks = None
        existing.submitted_at = None
        existing.approved_at = None
        existing.is_deleted = False
        existing.deleted_at = None
        existing.updated_by = current_user.id
        db.commit()
        db.refresh(existing)
        log_audit(
            db, user=current_user, action="RESTORE", module=MODULE_AFE,
            entity_id=existing.id, entity_code=code,
            details=f"Restored deleted AFE {code} on create", request=request,
        )
        return afe_estimation.build_afe_out(existing)

    afe = Afe(
        afe_code=code,
        afe_name=payload.afe_name.strip(),
        afe_type=payload.afe_type,
        rig_id=rig.id,
        well_id=well.id,
        remarks=payload.remarks,
        status="draft",
        created_by=current_user.id,
        updated_by=current_user.id,
    )
    db.add(afe)
    db.commit()
    db.refresh(afe)
    log_audit(
        db, user=current_user, action="CREATE", module=MODULE_AFE,
        entity_id=afe.id, entity_code=code,
        details=f"Created AFE {code} - {afe.afe_name} ({afe.afe_type}) for well {well.well_code}",
        request=request,
    )
    return afe_estimation.build_afe_out(afe)


@router.put("/afes/{record_id}", response_model=AfeOut)
def update_afe(
    record_id: int,
    payload: AfeUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> AfeOut:
    afe = _get_afe(db, record_id)
    if afe.status != "draft":
        raise HTTPException(
            status_code=400,
            detail=f"AFE {afe.afe_code} is {afe.status} — reopen it as Draft before editing.",
        )

    if payload.afe_code and payload.afe_code.strip() != afe.afe_code:
        new_code = payload.afe_code.strip()
        clash = db.scalar(select(Afe).where(Afe.afe_code == new_code))
        if clash and clash.id != afe.id:
            raise HTTPException(status_code=400, detail=f"AFE code '{new_code}' already exists")
        afe.afe_code = new_code
    if payload.afe_name:
        afe.afe_name = payload.afe_name.strip()
    if payload.afe_type:
        afe.afe_type = payload.afe_type
    if payload.rig_id is not None or payload.well_id is not None:
        try:
            rig = _resolve_rig(db, payload.rig_id if payload.rig_id is not None else afe.rig_id)
            well = _resolve_well(db, payload.well_id if payload.well_id is not None else afe.well_id, rig.id)
        except AfeValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if afe.well_id != well.id and (afe.service_lines or afe.consumable_lines or afe.tangible_lines):
            raise HTTPException(
                status_code=400,
                detail="This AFE already has estimate lines — remove them before moving it to another well.",
            )
        afe.rig_id = rig.id
        afe.well_id = well.id
    if "remarks" in payload.model_fields_set:
        afe.remarks = payload.remarks

    afe.updated_by = current_user.id
    db.commit()
    db.refresh(afe)
    log_audit(
        db, user=current_user, action="UPDATE", module=MODULE_AFE,
        entity_id=afe.id, entity_code=afe.afe_code,
        details=f"Updated AFE {afe.afe_code}", request=request,
    )
    return afe_estimation.build_afe_out(afe)


@router.delete("/afes/{record_id}")
def soft_delete_afe(
    record_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> dict[str, Any]:
    afe = _get_afe(db, record_id)
    afe.is_deleted = True
    afe.deleted_at = datetime.now(UTC)
    afe.updated_by = current_user.id
    db.commit()
    log_audit(
        db, user=current_user, action="SOFT_DELETE", module=MODULE_AFE,
        entity_id=afe.id, entity_code=afe.afe_code,
        details=f"Soft deleted AFE {afe.afe_code}", request=request,
    )
    return {"status": "success", "message": "AFE moved to deleted entries"}


@router.post("/afes/{record_id}/restore")
def restore_afe(
    record_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> dict[str, Any]:
    afe = db.get(Afe, record_id)
    if not afe or not afe.is_deleted:
        raise HTTPException(status_code=404, detail="Deleted AFE not found")
    afe.is_deleted = False
    afe.deleted_at = None
    afe.updated_by = current_user.id
    db.commit()
    log_audit(
        db, user=current_user, action="RESTORE", module=MODULE_AFE,
        entity_id=afe.id, entity_code=afe.afe_code,
        details=f"Restored AFE {afe.afe_code}", request=request,
    )
    return {"status": "success", "message": "AFE restored"}


@router.delete("/afes/{record_id}/permanent")
def permanent_delete_afe(
    record_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> dict[str, Any]:
    afe = db.get(Afe, record_id)
    if not afe:
        raise HTTPException(status_code=404, detail="AFE not found")
    code = afe.afe_code
    db.delete(afe)
    db.commit()
    log_audit(
        db, user=current_user, action="PERMANENT_DELETE", module=MODULE_AFE,
        entity_id=record_id, entity_code=code,
        details=f"Permanently deleted AFE {code} and its estimate lines", request=request,
    )
    return {"status": "success", "message": "AFE permanently deleted"}


# ---------------------------------------------------------------------------
# AFE Cost Estimation tab
# ---------------------------------------------------------------------------


@router.get("/estimates", response_model=list[AfeOut])
def list_estimates(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    search: str | None = None,
) -> list[AfeOut]:
    """Every (non-deleted) AFE with its line counts and current estimated total."""

    return [afe_estimation.build_afe_out(afe) for afe in _list_afes(db, search=search)]


@router.get("/estimates/export")
def export_estimates(
    format: str = Query("xlsx", pattern="^(xlsx|csv)$"),
    include_deleted: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request = None,
) -> Response:
    """Every priced component of every AFE as one flat sheet."""

    afes = _list_afes(db, deleted=include_deleted)
    rows = afe_estimation.export_rows(db, afes)
    log_audit(
        db, user=current_user, action="EXPORT", module=MODULE_ESTIMATE,
        details=f"Exported {len(rows)} estimate rows for {len(afes)} AFEs as {format}", request=request,
    )
    return spreadsheet_response(rows, afe_estimation.EXPORT_HEADERS, "afe_cost_estimates", format)


@router.get("/estimates/{afe_id}", response_model=AfeEstimateOut)
def get_estimate(
    afe_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AfeEstimateOut:
    return afe_estimation.build_estimate_out(_get_afe(db, afe_id))


@router.get("/estimates/{afe_id}/export")
def export_single_estimate(
    afe_id: int,
    format: str = Query("xlsx", pattern="^(xlsx|csv)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request = None,
) -> Response:
    afe = _get_afe(db, afe_id)
    rows = afe_estimation.export_rows(db, [afe])
    log_audit(
        db, user=current_user, action="EXPORT", module=MODULE_ESTIMATE,
        details=f"Exported {len(rows)} estimate rows for AFE {afe.afe_code} as {format}", request=request,
    )
    return spreadsheet_response(rows, afe_estimation.EXPORT_HEADERS, f"afe_{afe.afe_code}_estimate", format)


@router.put("/estimates/{afe_id}", response_model=AfeEstimateOut)
def save_estimate(
    afe_id: int,
    payload: EstimateIn,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> AfeEstimateOut:
    afe = _get_afe(db, afe_id)
    try:
        result = afe_estimation.save_estimate(db, afe, payload, current_user)
    except AfeValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    log_audit(
        db, user=current_user, action="UPDATE", module=MODULE_ESTIMATE,
        entity_id=afe.id, entity_code=afe.afe_code,
        details=(
            f"Saved cost estimate for AFE {afe.afe_code}: {len(payload.services)} service(s), "
            f"{len(payload.consumables)} consumable(s), {len(payload.tangibles)} tangible(s) "
            f"— total {result.grand_total}"
        ),
        request=request,
    )
    return result


@router.post("/estimates/{afe_id}/preview")
def preview_estimate(
    afe_id: int,
    payload: EstimateIn,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Price an unsaved estimate.

    The cost estimation tab calls this (debounced) so the totals on screen are
    produced by the same engine that saves them — the money rules are never
    re-implemented in the browser. Nothing is written and nothing is audited.
    """

    afe = _get_afe(db, afe_id)
    try:
        return afe_estimation.preview_estimate(db, afe, payload)
    except AfeValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/estimates/{afe_id}/status", response_model=AfeOut)
def change_estimate_status(
    afe_id: int,
    payload: AfeStatusIn,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> AfeOut:
    afe = _get_afe(db, afe_id)
    try:
        afe, detail = afe_estimation.change_status(db, afe, payload.action, payload.remarks, current_user)
    except AfeValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    log_audit(
        db, user=current_user, action="UPDATE", module=MODULE_ESTIMATE,
        entity_id=afe.id, entity_code=afe.afe_code, details=detail, request=request,
    )
    return afe_estimation.build_afe_out(afe)
