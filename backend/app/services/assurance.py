"""Cross-module structural invariant checks for Phase 11 framework assurance."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.models.afe import AfeSnapshotAttempt
from app.models.calculations import EstimateCalculation
from app.models.cost_control import CostControlBatch, CostControlPostAttempt, CostTransaction
from app.models.workflow import EstimateWorkflowInstance, WorkflowProfile, WorkflowTransitionAttempt
from app.schemas.assurance import AssuranceBlocker, AssuranceCheck, AssuranceStatus


class AssuranceService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def status(self) -> AssuranceStatus:
        checks = [
            self._check(
                "blocked_calculation_output",
                "Blocked calculations have no output",
                self._count(
                    select(func.count())
                    .select_from(EstimateCalculation)
                    .where(
                        EstimateCalculation.status == "blocked",
                        EstimateCalculation.output_snapshot.is_not(None),
                    )
                ),
                "Blocked calculation runs must retain input but no financial output.",
            ),
            self._check(
                "pending_workflow_instances",
                "No workflow instance without a published profile",
                self._workflow_instance_violations(),
                "The pending workflow policy cannot create active state.",
            ),
            self._check(
                "blocked_afe_result",
                "Blocked AFE attempts create no snapshot",
                self._count(
                    select(func.count())
                    .select_from(AfeSnapshotAttempt)
                    .where(
                        AfeSnapshotAttempt.status == "blocked",
                        AfeSnapshotAttempt.resulting_snapshot_id.is_not(None),
                    )
                ),
                "Blocked baseline requests must not issue an AFE.",
            ),
            self._check(
                "blocked_post_transactions",
                "Blocked cost batches post no transactions",
                self._blocked_post_violations(),
                "A blocked post attempt cannot produce immutable cost transactions.",
            ),
            self._check(
                "transition_attempt_actor",
                "Transition attempts retain actors",
                self._count(
                    select(func.count())
                    .select_from(WorkflowTransitionAttempt)
                    .where(WorkflowTransitionAttempt.created_by.is_(None))
                ),
                "Every transition attempt must be actor-attributed.",
            ),
            self._check(
                "post_attempt_actor",
                "Post attempts retain actors",
                self._count(
                    select(func.count())
                    .select_from(CostControlPostAttempt)
                    .where(CostControlPostAttempt.created_by.is_(None))
                ),
                "Every cost-state post attempt must be actor-attributed.",
            ),
        ]
        blockers = [
            AssuranceBlocker(
                key="numeric_reconciliation",
                status="blocked",
                detail="Certified workbook scenarios and expected outputs are unavailable.",
            ),
            AssuranceBlocker(
                key="business_formulas",
                status="blocked",
                detail="Full-chain calculation formulas remain pending.",
            ),
            AssuranceBlocker(
                key="production_role_matrix",
                status="blocked",
                detail="Organization roles, delegation, and separation of duties are unapproved.",
            ),
            AssuranceBlocker(
                key="production_reporting_access",
                status="blocked",
                detail=(
                    "Database principal, grants, RLS, gateway, and refresh policy are unapproved."
                ),
            ),
        ]
        return AssuranceStatus(
            status="framework_ready" if all(item.violations == 0 for item in checks) else "failed",
            migration_head="20260813_0010",
            reporting_contract_version="1.0",
            checks=checks,
            blockers=blockers,
        )

    def _workflow_instance_violations(self) -> int:
        published = self._count(
            select(func.count())
            .select_from(WorkflowProfile)
            .where(WorkflowProfile.lifecycle_status == "published")
        )
        if published:
            return 0
        return self._count(select(func.count()).select_from(EstimateWorkflowInstance))

    def _blocked_post_violations(self) -> int:
        blocked_batch_ids = select(CostControlPostAttempt.batch_id).where(
            CostControlPostAttempt.status == "blocked"
        )
        return self._count(
            select(func.count())
            .select_from(CostTransaction)
            .where(CostTransaction.source_batch_id.in_(blocked_batch_ids))
        ) + self._count(
            select(func.count())
            .select_from(CostControlBatch)
            .where(
                CostControlBatch.id.in_(blocked_batch_ids),
                CostControlBatch.posted_rows > 0,
            )
        )

    def _count(self, statement: Select[tuple[int]]) -> int:
        value = self.session.scalar(statement)
        return int(value or 0)

    @staticmethod
    def _check(key: str, label: str, violations: int, detail: str) -> AssuranceCheck:
        return AssuranceCheck(
            key=key,
            label=label,
            status="passed" if violations == 0 else "failed",
            violations=violations,
            detail=detail,
        )
