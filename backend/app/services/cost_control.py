"""Bulk cost-state staging, Excel preview, posting audit, and lineage boundaries."""

import hashlib
from io import BytesIO
from typing import Any, cast
from uuid import UUID

from fastapi.encoders import jsonable_encoder
from openpyxl import Workbook
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import (
    BusinessValidationError,
    CostStatePolicyPendingError,
    NotFoundError,
)
from app.domain.cost_control.posting import post_cost_batch
from app.domain.cost_control.types import (
    CorrectionKind,
    CostEntryInput,
    CostPostingInput,
    CostPostingResult,
    CostState,
)
from app.integrations.excel.mapper import ExcelMapper
from app.integrations.excel.reader import ExcelReader
from app.models.afe import AfeSnapshot
from app.models.cost_control import (
    CostControlBatch,
    CostControlBatchError,
    CostControlPostAttempt,
    CostControlStagedLine,
    CostTransaction,
)
from app.models.estimates import EstimateVersion
from app.models.master_data import CostCode, Currency, Unit, Vendor
from app.models.user import User
from app.schemas.cost_control import (
    CostControlBatchCreate,
    CostControlBatchErrorRead,
    CostControlBatchPage,
    CostControlBatchRead,
    CostControlImportPreview,
    CostControlLineInput,
    CostControlPostAttemptRead,
    CostControlStagedLineRead,
)

COST_STATE_POLICY_VERSION = "pending-all-cost-states"
PENDING_COST_STATE_REQUIREMENTS = [
    "authoritative definition and recognition point for each of the five cost states",
    "issued AFE eligibility and shared-dimension allocation rules",
    "source-document identity, duplicate detection, matching, and cut-off rules",
    "currency, tax, gross/net, sign, precision, and accounting-date treatment",
    "state-to-state reconciliation and forecast/EAC methodology",
    "reversal and adjustment authorization, amount, date, and period behavior",
]
TEMPLATE_HEADERS = [
    "transaction_date",
    "source_document_type",
    "source_document_reference",
    "external_transaction_id",
    "cost_code",
    "vendor_code",
    "description",
    "quantity",
    "unit_code",
    "currency_code",
    "amount",
    "correction_kind",
    "reverses_transaction_id",
]


class CostControlService:
    def __init__(self, session: Session, actor: User) -> None:
        self.session, self.actor = session, actor

    def stage_manual(self, request: CostControlBatchCreate) -> CostControlBatchRead:
        self._version(request.estimate_version_id)
        rows = [row.model_dump(mode="python") for row in request.rows]
        batch = self._stage(
            estimate_version_id=request.estimate_version_id,
            cost_state=request.cost_state,
            source_type="manual",
            rows=rows,
            filename=None,
            file_sha256=None,
        )
        return self._batch_read(batch)

    def preview_excel(
        self,
        *,
        estimate_version_id: UUID,
        cost_state: CostState,
        filename: str,
        content: bytes,
        sheet_name: str | None,
    ) -> CostControlImportPreview:
        self._version(estimate_version_id)
        workbook = ExcelReader().read(content, filename, sheet_name)
        mapped = ExcelMapper().map("cost-control-lines", workbook.columns, workbook.rows)
        batch = self._stage(
            estimate_version_id=estimate_version_id,
            cost_state=cost_state,
            source_type="excel",
            rows=mapped.rows,
            filename=filename,
            file_sha256=hashlib.sha256(content).hexdigest(),
        )
        return CostControlImportPreview(
            batch=self._batch_read(batch),
            detected_columns=mapped.detected_columns,
            applied_mapping=mapped.applied_mapping,
        )

    def post(self, batch_id: UUID) -> CostControlBatchRead:
        batch = self._batch(batch_id)
        if batch.status not in {"validated", "blocked"} or batch.error_rows:
            raise BusinessValidationError("Only a fully validated cost-control batch can post")
        source = self._posting_input(batch)
        attempt = CostControlPostAttempt(
            batch_id=batch.id,
            status="blocked",
            policy_snapshot={
                "cost_state_policy_version": COST_STATE_POLICY_VERSION,
                "batch_id": str(batch.id),
                "cost_state": batch.cost_state,
                "estimate_version_id": str(batch.estimate_version_id),
                "afe_snapshot_id": str(batch.afe_snapshot_id) if batch.afe_snapshot_id else None,
                "source_type": batch.source_type,
                "valid_rows": batch.valid_rows,
                "error_rows": batch.error_rows,
                "correction_kinds": sorted({line.correction_kind for line in batch.staged_lines}),
            },
            created_by=self.actor.id,
            updated_by=self.actor.id,
        )
        self.session.add(attempt)
        self.session.flush()
        try:
            result = post_cost_batch(source)
        except NotImplementedError as exc:
            batch.status = "blocked"
            batch.updated_by = self.actor.id
            attempt.message = str(exc)
            self.session.commit()
            self.session.expire(batch, ["post_attempts"])
            raise CostStatePolicyPendingError(
                "Cost-state posting is blocked pending approved recognition, allocation, "
                "reconciliation, and reversal rules",
                {
                    "post_attempt_id": str(attempt.id),
                    "cost_state_policy_version": COST_STATE_POLICY_VERSION,
                    "pending_requirements": PENDING_COST_STATE_REQUIREMENTS,
                },
            ) from exc
        self._persist_postings(batch, result)
        attempt.status = "completed"
        attempt.message = "Immutable cost-state records posted"
        batch.status = "committed"
        batch.posted_rows = len(result.entries)
        batch.updated_by = self.actor.id
        self.session.commit()
        return self._batch_read(batch)

    def get(self, batch_id: UUID) -> CostControlBatchRead:
        return self._batch_read(self._batch(batch_id))

    def list_batches(self) -> CostControlBatchPage:
        batches = list(
            self.session.scalars(
                select(CostControlBatch).order_by(CostControlBatch.created_at.desc())
            ).all()
        )
        return CostControlBatchPage(
            items=[self._batch_read(batch) for batch in batches], total=len(batches)
        )

    @staticmethod
    def template() -> bytes:
        workbook = Workbook()
        sheet = workbook.active
        if sheet is None:
            raise RuntimeError("Workbook did not create its default worksheet")
        sheet.title = "Cost Control"
        sheet.append(TEMPLATE_HEADERS)
        stream = BytesIO()
        workbook.save(stream)
        return stream.getvalue()

    def _stage(
        self,
        *,
        estimate_version_id: UUID,
        cost_state: CostState,
        source_type: str,
        rows: list[dict[str, Any]],
        filename: str | None,
        file_sha256: str | None,
    ) -> CostControlBatch:
        afe = self.session.scalar(
            select(AfeSnapshot).where(AfeSnapshot.estimate_version_id == estimate_version_id)
        )
        batch = CostControlBatch(
            estimate_version_id=estimate_version_id,
            afe_snapshot_id=afe.id if afe else None,
            cost_state=cost_state,
            source_type=source_type,
            filename=filename,
            file_sha256=file_sha256,
            mapping_profile="cost-control-lines-default",
            mapping_version="1.0",
            status="validated",
            total_rows=len(rows),
            valid_rows=0,
            error_rows=0,
            posted_rows=0,
            created_by=self.actor.id,
            updated_by=self.actor.id,
        )
        self.session.add(batch)
        self.session.flush()
        invalid_rows: set[int] = set()
        reference_catalog = self._reference_catalog()
        for index, raw in enumerate(rows, start=1):
            try:
                line = CostControlLineInput.model_validate(self._normalize(raw))
                self._validate_references(line, reference_catalog)
                batch.staged_lines.append(self._staged_line(batch.id, index, line, raw))
            except (ValueError, ValidationError) as exc:
                invalid_rows.add(index)
                batch.errors.append(
                    CostControlBatchError(
                        row_number=index,
                        error_code="row_validation_error",
                        message=str(exc),
                        raw_value=jsonable_encoder(raw),
                        created_by=self.actor.id,
                        updated_by=self.actor.id,
                    )
                )
        batch.valid_rows = len(rows) - len(invalid_rows)
        batch.error_rows = len(invalid_rows)
        batch.status = "invalid" if invalid_rows else "validated"
        self.session.commit()
        self.session.refresh(batch)
        return batch

    def _reference_catalog(self) -> dict[str, set[str]]:
        return {
            "cost_code": set(self.session.scalars(select(CostCode.code)).all()),
            "currency_code": set(self.session.scalars(select(Currency.code)).all()),
            "vendor_code": set(self.session.scalars(select(Vendor.code)).all()),
            "unit_code": set(self.session.scalars(select(Unit.code)).all()),
        }

    @staticmethod
    def _validate_references(line: CostControlLineInput, catalog: dict[str, set[str]]) -> None:
        checks: list[tuple[str, str]] = [
            ("cost_code", line.cost_code),
            ("currency_code", line.currency_code),
        ]
        if line.vendor_code:
            checks.append(("vendor_code", line.vendor_code))
        if line.unit_code:
            checks.append(("unit_code", line.unit_code))
        for field, value in checks:
            code = value.strip().upper()
            if code not in catalog[field]:
                raise ValueError(f"{field} '{code}' does not exist")

    @staticmethod
    def _normalize(raw: dict[str, Any]) -> dict[str, Any]:
        values = {key: value for key, value in raw.items() if value not in (None, "")}
        for field in ("cost_code", "vendor_code", "unit_code", "currency_code"):
            if field in values:
                values[field] = str(values[field]).strip().upper()
        if "correction_kind" in values:
            values["correction_kind"] = str(values["correction_kind"]).strip().lower()
        return values

    def _staged_line(
        self,
        batch_id: UUID,
        row_number: int,
        line: CostControlLineInput,
        raw: dict[str, Any],
    ) -> CostControlStagedLine:
        return CostControlStagedLine(
            batch_id=batch_id,
            row_number=row_number,
            transaction_date=line.transaction_date,
            source_document_type=line.source_document_type.strip(),
            source_document_reference=line.source_document_reference.strip(),
            external_transaction_id=line.external_transaction_id,
            cost_code=line.cost_code.strip().upper(),
            vendor_code=line.vendor_code.strip().upper() if line.vendor_code else None,
            description=line.description.strip(),
            quantity=line.quantity,
            unit_code=line.unit_code.strip().upper() if line.unit_code else None,
            currency_code=line.currency_code.strip().upper(),
            amount=line.amount,
            correction_kind=line.correction_kind,
            reverses_transaction_id=line.reverses_transaction_id,
            raw_snapshot=jsonable_encoder(raw),
            created_by=self.actor.id,
            updated_by=self.actor.id,
        )

    @staticmethod
    def _posting_input(batch: CostControlBatch) -> CostPostingInput:
        return CostPostingInput(
            batch_id=str(batch.id),
            estimate_version_id=str(batch.estimate_version_id),
            afe_snapshot_id=str(batch.afe_snapshot_id) if batch.afe_snapshot_id else None,
            cost_state=cast(CostState, batch.cost_state),
            entries=tuple(
                CostEntryInput(
                    staged_line_id=str(line.id),
                    row_number=line.row_number,
                    cost_state=cast(CostState, batch.cost_state),
                    transaction_date=line.transaction_date,
                    source_document_type=line.source_document_type,
                    source_document_reference=line.source_document_reference,
                    external_transaction_id=line.external_transaction_id,
                    cost_code=line.cost_code,
                    vendor_code=line.vendor_code,
                    description=line.description,
                    quantity=line.quantity,
                    unit_code=line.unit_code,
                    currency_code=line.currency_code,
                    amount=line.amount,
                    correction_kind=cast(CorrectionKind, line.correction_kind),
                    reverses_transaction_id=(
                        str(line.reverses_transaction_id) if line.reverses_transaction_id else None
                    ),
                )
                for line in batch.staged_lines
            ),
        )

    def _persist_postings(self, batch: CostControlBatch, result: CostPostingResult) -> None:
        if batch.afe_snapshot_id is None:
            raise ValueError("An issued AFE snapshot is required before cost-state posting")
        by_id = {str(line.id): line for line in batch.staged_lines}
        for posted in result.entries:
            line = by_id[posted.staged_line_id]
            self.session.add(
                CostTransaction(
                    posting_reference=posted.posting_reference,
                    afe_snapshot_id=batch.afe_snapshot_id,
                    source_batch_id=batch.id,
                    source_staged_line_id=line.id,
                    cost_state=batch.cost_state,
                    transaction_date=line.transaction_date,
                    source_document_type=line.source_document_type,
                    source_document_reference=line.source_document_reference,
                    external_transaction_id=line.external_transaction_id,
                    cost_code=line.cost_code,
                    vendor_code=line.vendor_code,
                    description=line.description,
                    quantity=line.quantity,
                    unit_code=line.unit_code,
                    currency_code=line.currency_code,
                    amount=posted.amount,
                    correction_kind=line.correction_kind,
                    reverses_transaction_id=line.reverses_transaction_id,
                    created_by=self.actor.id,
                    updated_by=self.actor.id,
                )
            )

    def _version(self, version_id: UUID) -> EstimateVersion:
        version = self.session.get(EstimateVersion, version_id)
        if version is None:
            raise NotFoundError("Estimate version not found")
        return version

    def _batch(self, batch_id: UUID) -> CostControlBatch:
        batch = self.session.get(CostControlBatch, batch_id)
        if batch is None:
            raise NotFoundError("Cost-control batch not found")
        return batch

    @staticmethod
    def _batch_read(batch: CostControlBatch) -> CostControlBatchRead:
        return CostControlBatchRead(
            id=batch.id,
            estimate_version_id=batch.estimate_version_id,
            afe_snapshot_id=batch.afe_snapshot_id,
            cost_state=batch.cost_state,
            source_type=batch.source_type,
            filename=batch.filename,
            mapping_profile=batch.mapping_profile,
            mapping_version=batch.mapping_version,
            status=batch.status,
            total_rows=batch.total_rows,
            valid_rows=batch.valid_rows,
            error_rows=batch.error_rows,
            posted_rows=batch.posted_rows,
            staged_lines=[
                CostControlStagedLineRead.model_validate(line) for line in batch.staged_lines
            ],
            errors=[CostControlBatchErrorRead.model_validate(error) for error in batch.errors],
            post_attempts=[
                CostControlPostAttemptRead.model_validate(attempt)
                for attempt in sorted(
                    batch.post_attempts, key=lambda item: item.created_at, reverse=True
                )
            ],
            created_at=batch.created_at,
            created_by=batch.created_by,
        )
