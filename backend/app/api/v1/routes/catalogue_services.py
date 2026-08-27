"""Services catalogue API (Services group).

Common template: list / create / update / soft-delete / restore / permanent
delete, bulk import with flexible templates, xlsx/csv export and full audit.
Service codes are auto-generated server-side.
"""

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db
from app.models.catalogue import Service
from app.models.master_data import VendorSupplier
from app.models.user import User
from app.schemas.catalogue import ServiceOut
from app.schemas.master_data import BulkImportResponse
from app.services.audit import log_audit
from app.services.import_helpers import (
    read_tabular_file,
    row_get,
    spreadsheet_response,
    template_xlsx_response,
)

router = APIRouter(prefix="/catalogue/services", tags=["catalogue-services"])

MODULE_NAME = "Services"
CODE_PREFIX = "SVC"
PROVIDER_TYPES = {"Inhouse", "3rd Party"}


def _next_code(db: Session) -> str:
    """Generate the next service code, e.g. SVC-0001, ignoring soft-deleted gaps."""

    highest = 0
    rows = db.scalars(select(Service.service_code)).all()
    for code in rows:
        digits = "".join(ch for ch in str(code) if ch.isdigit())
        if digits:
            highest = max(highest, int(digits))
    return f"{CODE_PREFIX}-{highest + 1:04d}"


def _build_out(svc: Service) -> ServiceOut:
    vendor = svc.vendor
    vendor_code = vendor.vendor_code if vendor else None
    vendor_name = vendor.vendor_name if vendor else None
    vendor_display = f"{vendor_code} - {vendor_name}" if vendor_code and vendor_name else vendor_code or vendor_name
    return ServiceOut(
        id=svc.id,
        service_code=svc.service_code,
        service_name=svc.service_name,
        service_type=svc.service_type or "Service",
        provider_type=svc.provider_type,
        vendor_id=svc.vendor_id,
        vendor_code=vendor_code,
        vendor_name=vendor_name,
        vendor_display=vendor_display,
        description=svc.description,
        is_deleted=svc.is_deleted,
        deleted_at=svc.deleted_at,
        created_at=svc.created_at,
        updated_at=svc.updated_at,
    )


def _resolve_vendor(db: Session, ref: Any) -> VendorSupplier | None:
    """Resolve a vendor by id, code (exact then case-insensitive) or fuzzy name."""

    if ref is None or str(ref).strip() == "":
        return None
    ref = str(ref).strip()
    try:
        vendor = db.get(VendorSupplier, int(ref))
        if vendor and not vendor.is_deleted:
            return vendor
    except (ValueError, TypeError):
        pass
    vendor = db.scalar(
        select(VendorSupplier).where(VendorSupplier.vendor_code == ref, VendorSupplier.is_deleted == False)
    )
    if vendor:
        return vendor
    vendor = db.scalar(
        select(VendorSupplier).where(VendorSupplier.vendor_code.ilike(ref), VendorSupplier.is_deleted == False)
    )
    if vendor:
        return vendor
    return db.scalar(
        select(VendorSupplier).where(
            VendorSupplier.vendor_name.ilike(f"%{ref}%"),
            VendorSupplier.is_deleted == False,
        )
    )


def _normalize_provider_type(value: Any) -> str:
    val = str(value or "").strip().lower().replace(" ", "").replace("-", "").replace("_", "")
    if val in {"inhouse", "in", "internal"}:
        return "Inhouse"
    if val in {"3rdparty", "thirdparty", "3p", "external", "outsource", "outsourced"}:
        return "3rd Party"
    raise ValueError(f"Provider Type must be 'Inhouse' or '3rd Party' (got '{value}')")


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


@router.get("", response_model=list[ServiceOut])
def list_services(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    search: str | None = None,
    provider_type: str | None = None,
) -> list[ServiceOut]:
    stmt = select(Service).where(Service.is_deleted == False)
    if provider_type:
        stmt = stmt.where(Service.provider_type == provider_type)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            or_(Service.service_name.ilike(like), Service.service_code.ilike(like), Service.description.ilike(like))
        )
    stmt = stmt.order_by(Service.id.desc())
    return [_build_out(s) for s in db.scalars(stmt).all()]


@router.get("/deleted", response_model=list[ServiceOut])
def list_deleted_services(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[ServiceOut]:
    stmt = select(Service).where(Service.is_deleted == True).order_by(Service.deleted_at.desc())
    return [_build_out(s) for s in db.scalars(stmt).all()]


@router.get("/export")
def export_services(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
    format: str = Query("xlsx", pattern="^(xlsx|csv)$"),
) -> Response:
    records = db.scalars(
        select(Service).where(Service.is_deleted == False).order_by(Service.service_code)
    ).all()
    log_audit(db, user=current_user, action="EXPORT", module=MODULE_NAME,
              details=f"Exported {len(records)} services as {format}", request=request)
    headers = ["service_code", "service_name", "provider_type", "vendor_code", "vendor_name", "description"]
    rows = [
        [s.service_code, s.service_name, s.provider_type,
         s.vendor.vendor_code if s.vendor else "", s.vendor.vendor_name if s.vendor else "",
         s.description or ""]
        for s in records
    ]
    return spreadsheet_response(rows, headers, "services_export", format)


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def _apply_service_fields(db: Session, svc: Service, payload: dict[str, Any]) -> None:
    name = str(payload.get("service_name") or payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Service Name is required")

    provider_raw = payload.get("provider_type")
    if not provider_raw:
        raise HTTPException(status_code=400, detail="Provider Type is required (Inhouse / 3rd Party)")
    try:
        provider_type = _normalize_provider_type(provider_raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    vendor_id: int | None = None
    vendor_ref = payload.get("vendor_id") if payload.get("vendor_id") not in (None, "") else payload.get("vendor")
    if provider_type == "3rd Party" and not vendor_ref:
        raise HTTPException(status_code=400, detail="Service Provider is required for 3rd Party services")
    if vendor_ref:
        vendor = _resolve_vendor(db, vendor_ref)
        if not vendor:
            raise HTTPException(status_code=400, detail=f"Service Provider/Vendor '{vendor_ref}' not found")
        vendor_id = vendor.id

    svc.service_name = name
    svc.provider_type = provider_type
    svc.vendor_id = vendor_id
    svc.description = payload.get("description") or None
    if not svc.service_type:
        svc.service_type = "Service"


@router.post("", response_model=ServiceOut)
def create_service(
    payload: dict[str, Any],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> ServiceOut:
    name = str(payload.get("service_name") or payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Service Name is required")

    dup = db.scalar(
        select(Service).where(
            func.lower(Service.service_name) == name.lower(),
            Service.is_deleted == False,
        )
    )
    if dup:
        raise HTTPException(status_code=400, detail=f"Service '{name}' already exists (code {dup.service_code})")

    svc = Service(service_code=_next_code(db), created_by=current_user.id, updated_by=current_user.id)
    _apply_service_fields(db, svc, payload)
    db.add(svc)
    db.commit()
    db.refresh(svc)
    log_audit(db, user=current_user, action="CREATE", module=MODULE_NAME, entity_id=svc.id,
              entity_code=svc.service_code, details=f"Created service {svc.service_code} - {svc.service_name}",
              request=request)
    return _build_out(svc)


@router.put("/{record_id}", response_model=ServiceOut)
def update_service(
    record_id: int,
    payload: dict[str, Any],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> ServiceOut:
    svc = db.get(Service, record_id)
    if not svc or svc.is_deleted:
        raise HTTPException(status_code=404, detail="Service not found")

    new_name = str(payload.get("service_name") or payload.get("name") or svc.service_name).strip()
    if new_name.lower() != svc.service_name.lower():
        clash = db.scalar(
            select(Service).where(
                func.lower(Service.service_name) == new_name.lower(),
                Service.id != record_id,
                Service.is_deleted == False,
            )
        )
        if clash:
            raise HTTPException(status_code=400, detail=f"Service '{new_name}' already exists")

    _apply_service_fields(db, svc, payload)
    svc.updated_by = current_user.id
    db.commit()
    db.refresh(svc)
    log_audit(db, user=current_user, action="UPDATE", module=MODULE_NAME, entity_id=svc.id,
              entity_code=svc.service_code, details=f"Updated service {svc.service_code}", request=request)
    return _build_out(svc)


@router.delete("/{record_id}")
def soft_delete_service(
    record_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> dict[str, str]:
    svc = db.get(Service, record_id)
    if not svc or svc.is_deleted:
        raise HTTPException(status_code=404, detail="Service not found")
    svc.is_deleted = True
    svc.deleted_at = datetime.now(UTC)
    db.commit()
    log_audit(db, user=current_user, action="SOFT_DELETE", module=MODULE_NAME, entity_id=svc.id,
              entity_code=svc.service_code, details=f"Soft deleted service {svc.service_code}", request=request)
    return {"status": "success", "message": "Service moved to deleted entries"}


@router.post("/{record_id}/restore")
def restore_service(
    record_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> dict[str, str]:
    svc = db.get(Service, record_id)
    if not svc or not svc.is_deleted:
        raise HTTPException(status_code=404, detail="Deleted service not found")
    svc.is_deleted = False
    svc.deleted_at = None
    db.commit()
    log_audit(db, user=current_user, action="RESTORE", module=MODULE_NAME, entity_id=svc.id,
              entity_code=svc.service_code, details=f"Restored service {svc.service_code}", request=request)
    return {"status": "success", "message": "Service restored"}


@router.delete("/{record_id}/permanent")
def permanent_delete_service(
    record_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> dict[str, str]:
    svc = db.get(Service, record_id)
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")
    code = svc.service_code
    db.delete(svc)
    db.commit()
    log_audit(db, user=current_user, action="PERMANENT_DELETE", module=MODULE_NAME, entity_id=record_id,
              entity_code=code, details=f"Permanently deleted service {code}", request=request)
    return {"status": "success", "message": "Service permanently deleted"}


# ---------------------------------------------------------------------------
# Bulk import
# ---------------------------------------------------------------------------

IMPORT_HEADERS = ["service_name", "provider_type", "vendor_code", "description"]


@router.get("/import-template")
def download_services_template(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    """XLSX template — download, fill with data, upload the same file."""

    vendor_codes = [str(code) for code in db.scalars(
        select(VendorSupplier.vendor_code).where(VendorSupplier.is_deleted == False)
        .order_by(VendorSupplier.vendor_code)
    ).all()]
    return template_xlsx_response(
        "services_template",
        IMPORT_HEADERS,
        sample_rows=[
            ["Mud Logging Services", "3rd Party", "VEND001", "Mud logging while drilling"],
            ["Rig Maintenance", "Inhouse", "", "Scheduled rig maintenance by internal crew"],
        ],
        dropdowns={2: sorted(PROVIDER_TYPES), 3: vendor_codes},
        note="Service codes are generated automatically on import.",
    )


@router.post("/import", response_model=BulkImportResponse)
async def import_services(
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
    except Exception as exc:  # pragma: no cover - parse failures
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {exc}") from exc

    imported = 0
    errors: list[str] = []
    for r_num, row in rows:
        try:
            name = str(row_get(row, "service_name", "name", "service") or "").strip()
            if not name:
                raise ValueError("Service Name is required")
            provider_raw = row_get(row, "provider_type", "provider", "type")
            provider_type = _normalize_provider_type(provider_raw)
            vendor_ref = row_get(row, "vendor_code", "vendor", "supplier", "service_provider")
            vendor_id = None
            if vendor_ref:
                vendor = _resolve_vendor(db, vendor_ref)
                if not vendor:
                    raise ValueError(f"Vendor '{vendor_ref}' not found")
                vendor_id = vendor.id
            elif provider_type == "3rd Party":
                raise ValueError("Service Provider (vendor_code) is required for 3rd Party services")

            existing = db.scalar(
                select(Service).where(func.lower(Service.service_name) == name.lower())
            )
            if existing:
                if existing.is_deleted:
                    existing.is_deleted = False
                    existing.deleted_at = None
                existing.provider_type = provider_type
                existing.vendor_id = vendor_id
                desc = row_get(row, "description", "desc", "remarks")
                if desc:
                    existing.description = str(desc)
                existing.updated_by = current_user.id
            else:
                db.add(Service(
                    service_code=_next_code(db),
                    service_name=name,
                    service_type="Service",
                    provider_type=provider_type,
                    vendor_id=vendor_id,
                    description=(str(row_get(row, "description", "desc", "remarks")) or None),
                    created_by=current_user.id,
                    updated_by=current_user.id,
                ))
            imported += 1
            db.flush()
        except Exception as exc:
            errors.append(f"Row {r_num}: {exc}")

    db.commit()
    log_audit(db, user=current_user, action="BULK_IMPORT", module=MODULE_NAME,
              details=f"Imported {imported} services with {len(errors)} errors from {filename}", request=request)
    return BulkImportResponse(imported_count=imported, error_count=len(errors),
                              errors=errors[:30], success=not errors)
