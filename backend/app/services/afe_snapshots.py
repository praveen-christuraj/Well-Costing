"""Baseline AFE snapshot orchestration with explicit pending-policy auditing."""

from dataclasses import asdict
from uuid import UUID

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AfePolicyPendingError, ConflictError, NotFoundError
from app.domain.afe.snapshots import create_baseline_afe_snapshot
from app.domain.afe.types import AfeLineInput, BaselineAfeInput, BaselineAfeSnapshot
from app.models.afe_snapshots import AfeSnapshot, AfeSnapshotAttempt, AfeSnapshotLine
from app.models.calculations import EstimateCalculation
from app.models.estimates import CostEstimate, EstimateVersion
from app.models.user import User
from app.models.workflow import EstimateWorkflowInstance
from app.schemas.afe_snapshots import (
    AfeSnapshotAttemptRead,
    AfeSnapshotCreateRequest,
    AfeSnapshotLineRead,
    AfeSnapshotRead,
    EstimateAfeStatus,
)

AFE_POLICY_VERSION = "pending-baseline-afe"
PENDING_AFE_REQUIREMENTS = [
    "approved estimate workflow state and AFE eligibility gate",
    "completed calculation and accepted rule-set prerequisites",
    "AFE numbering, ownership, and duplicate-reference policy",
    "authoritative header, line, assumption, and attachment snapshot contents",
    "issue date, authorization actor, status, and accounting handoff semantics",
    "void, cancellation, correction, and duplicate-attempt treatment",
]


class EstimateAfeService:
    def __init__(self, session: Session, actor: User) -> None:
        self.session, self.actor = session, actor

    def status(self, estimate_id: UUID, version_id: UUID | None = None) -> EstimateAfeStatus:
        estimate, version = self._estimate_version(estimate_id, version_id)
        snapshot = self.session.scalar(
            select(AfeSnapshot).where(AfeSnapshot.estimate_version_id == version.id)
        )
        attempts = list(
            self.session.scalars(
                select(AfeSnapshotAttempt)
                .where(AfeSnapshotAttempt.estimate_version_id == version.id)
                .order_by(AfeSnapshotAttempt.created_at.desc())
            ).all()
        )
        return EstimateAfeStatus(
            estimate_id=estimate.id,
            estimate_version_id=version.id,
            version_number=version.version_number,
            afe_status="issued" if snapshot else "policy_pending",
            baseline_snapshot=self._snapshot_read(snapshot) if snapshot else None,
            creation_attempts=[
                AfeSnapshotAttemptRead.model_validate(attempt) for attempt in attempts
            ],
            pending_requirements=[] if snapshot else PENDING_AFE_REQUIREMENTS,
        )

    def create_baseline(
        self, estimate_id: UUID, request: AfeSnapshotCreateRequest
    ) -> EstimateAfeStatus:
        estimate, version = self._estimate_version(estimate_id, request.version_id)
        existing = self.session.scalar(
            select(AfeSnapshot).where(AfeSnapshot.estimate_version_id == version.id)
        )
        if existing is not None:
            raise ConflictError("A baseline AFE snapshot already exists for this estimate version")
        calculation = self.session.scalar(
            select(EstimateCalculation)
            .where(EstimateCalculation.estimate_version_id == version.id)
            .order_by(EstimateCalculation.created_at.desc())
        )
        workflow = self.session.scalar(
            select(EstimateWorkflowInstance).where(
                EstimateWorkflowInstance.estimate_version_id == version.id
            )
        )
        source = self._source(estimate, version, calculation)
        attempt = AfeSnapshotAttempt(
            estimate_version_id=version.id,
            requested_reference=request.requested_reference,
            status="blocked",
            eligibility_snapshot={
                "afe_policy_version": AFE_POLICY_VERSION,
                "estimate_id": str(estimate.id),
                "estimate_version_id": str(version.id),
                "version_number": version.version_number,
                "estimate_status": version.status,
                "workflow_instance_id": str(workflow.id) if workflow else None,
                "workflow_profile_id": str(workflow.workflow_profile_id) if workflow else None,
                "workflow_state_key": workflow.current_state_key if workflow else None,
                "calculation_run_id": str(calculation.id) if calculation else None,
                "calculation_status": calculation.status if calculation else None,
                "rule_set_version": calculation.rule_set_version if calculation else None,
                "totals_complete": all(
                    value is not None
                    for value in (
                        version.base_total,
                        version.contingency_total,
                        version.escalation_total,
                        version.grand_total,
                    )
                ),
                "line_totals_complete": all(item.total_cost is not None for item in version.items),
            },
            created_by=self.actor.id,
            updated_by=self.actor.id,
        )
        self.session.add(attempt)
        self.session.flush()
        try:
            result = create_baseline_afe_snapshot(source)
        except NotImplementedError as exc:
            attempt.message = str(exc)
            self.session.commit()
            raise AfePolicyPendingError(
                "Baseline AFE creation is blocked pending an approved eligibility "
                "and snapshot policy",
                {
                    "snapshot_attempt_id": str(attempt.id),
                    "afe_policy_version": AFE_POLICY_VERSION,
                    "pending_requirements": PENDING_AFE_REQUIREMENTS,
                },
            ) from exc
        snapshot = self._persist(source, result)
        attempt.status = "completed"
        attempt.resulting_snapshot_id = snapshot.id
        attempt.message = "Immutable baseline AFE snapshot created"
        self.session.commit()
        return self.status(estimate_id, version.id)

    def get_snapshot(self, snapshot_id: UUID) -> AfeSnapshotRead:
        snapshot = self.session.get(AfeSnapshot, snapshot_id)
        if snapshot is None:
            raise NotFoundError("AFE snapshot not found")
        return self._snapshot_read(snapshot)

    def _estimate_version(
        self, estimate_id: UUID, version_id: UUID | None
    ) -> tuple[CostEstimate, EstimateVersion]:
        estimate = self.session.get(CostEstimate, estimate_id)
        if estimate is None:
            raise NotFoundError("Estimate not found")
        if version_id is None:
            version = next(
                (
                    item
                    for item in estimate.versions
                    if item.version_number == estimate.current_version_number
                ),
                None,
            )
        else:
            version = next((item for item in estimate.versions if item.id == version_id), None)
        if version is None:
            raise NotFoundError("Estimate version not found")
        return estimate, version

    @staticmethod
    def _source(
        estimate: CostEstimate,
        version: EstimateVersion,
        calculation: EstimateCalculation | None,
    ) -> BaselineAfeInput:
        lines: list[AfeLineInput] = []
        for item in version.items:
            catalog_item = item.catalog_item
            cost_code = item.cost_code
            unit = item.unit
            if catalog_item is None or cost_code is None or unit is None:
                # A referenced catalogue item/cost code/unit is missing; it cannot be
                # snapshotted, so skip it rather than crash.
                continue
            lines.append(
                AfeLineInput(
                    estimate_item_id=str(item.id),
                    line_number=item.line_number,
                    item_code=catalog_item.code,
                    item_description=catalog_item.name,
                    item_type=catalog_item.item_type,
                    cost_code=cost_code.code,
                    cost_category_code=(
                        catalog_item.cost_category.code if catalog_item.cost_category else None
                    ),
                    vendor_code=item.vendor.code if item.vendor else None,
                    quantity=item.quantity,
                    unit_code=unit.code,
                    rate_amount=item.rate.amount if item.rate else None,
                    rate_currency_code=(
                        item.rate.currency.code if item.rate and item.rate.currency else None
                    ),
                    base_cost=item.base_cost,
                    contingency_cost=item.contingency_cost,
                    escalation_cost=item.escalation_cost,
                    total_cost=item.total_cost,
                )
            )
        return BaselineAfeInput(
            estimate_id=str(estimate.id),
            estimate_version_id=str(version.id),
            estimate_code=estimate.code,
            estimate_title=estimate.title,
            afe_code=estimate.afe.code,
            project_code=estimate.afe.well.project.code,
            well_code=estimate.afe.well.code,
            currency_code=estimate.currency.code,
            calculation_run_id=str(calculation.id) if calculation else None,
            engine_version=calculation.engine_version if calculation else None,
            rule_set_version=calculation.rule_set_version if calculation else None,
            base_total=version.base_total,
            contingency_total=version.contingency_total,
            escalation_total=version.escalation_total,
            grand_total=version.grand_total,
            lines=tuple(lines),
        )

    def _persist(self, source: BaselineAfeInput, result: BaselineAfeSnapshot) -> AfeSnapshot:
        if source.engine_version is None or source.rule_set_version is None:
            raise ValueError("Completed calculation provenance is required for an AFE snapshot")
        snapshot = AfeSnapshot(
            afe_number=result.afe_number,
            estimate_version_id=UUID(result.estimate_version_id),
            calculation_run_id=UUID(result.calculation_run_id),
            issue_date=result.issue_date,
            estimate_code=source.estimate_code,
            estimate_title=source.estimate_title,
            afe_code=source.afe_code,
            project_code=source.project_code,
            well_code=source.well_code,
            currency_code=result.currency_code,
            engine_version=source.engine_version,
            rule_set_version=source.rule_set_version,
            base_total=result.base_total,
            contingency_total=result.contingency_total,
            escalation_total=result.escalation_total,
            grand_total=result.grand_total,
            source_snapshot=jsonable_encoder(asdict(source)),
            created_by=self.actor.id,
            updated_by=self.actor.id,
            lines=[
                AfeSnapshotLine(
                    source_estimate_item_id=UUID(line.source_estimate_item_id),
                    line_number=line.line_number,
                    item_code=line.item_code,
                    item_description=line.item_description,
                    item_type=line.item_type,
                    cost_code=line.cost_code,
                    cost_category_code=line.cost_category_code,
                    vendor_code=line.vendor_code,
                    quantity=line.quantity,
                    unit_code=line.unit_code,
                    rate_amount=line.rate_amount,
                    rate_currency_code=line.rate_currency_code,
                    base_cost=line.base_cost,
                    contingency_cost=line.contingency_cost,
                    escalation_cost=line.escalation_cost,
                    total_cost=line.total_cost,
                    created_by=self.actor.id,
                    updated_by=self.actor.id,
                )
                for line in result.lines
            ],
        )
        self.session.add(snapshot)
        self.session.flush()
        return snapshot

    @staticmethod
    def _snapshot_read(snapshot: AfeSnapshot) -> AfeSnapshotRead:
        return AfeSnapshotRead(
            id=snapshot.id,
            afe_number=snapshot.afe_number,
            snapshot_type=snapshot.snapshot_type,
            estimate_version_id=snapshot.estimate_version_id,
            calculation_run_id=snapshot.calculation_run_id,
            issue_date=snapshot.issue_date,
            estimate_code=snapshot.estimate_code,
            estimate_title=snapshot.estimate_title,
            afe_code=snapshot.afe_code,
            project_code=snapshot.project_code,
            well_code=snapshot.well_code,
            currency_code=snapshot.currency_code,
            engine_version=snapshot.engine_version,
            rule_set_version=snapshot.rule_set_version,
            base_total=snapshot.base_total,
            contingency_total=snapshot.contingency_total,
            escalation_total=snapshot.escalation_total,
            grand_total=snapshot.grand_total,
            source_snapshot=snapshot.source_snapshot,
            lines=[AfeSnapshotLineRead.model_validate(line) for line in snapshot.lines],
            created_at=snapshot.created_at,
            updated_at=snapshot.updated_at,
            created_by=snapshot.created_by,
            updated_by=snapshot.updated_by,
        )
