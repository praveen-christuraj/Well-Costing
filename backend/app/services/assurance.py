"""Integrity checks for the active well-costing data chain."""

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.models.afe import AfeLine
from app.models.afe_estimates import AfeCostEstimateLine
from app.models.daily_cost import DailyCostConsumableLine, DailyCostEntry, DailyCostServiceLine
from app.schemas.assurance import AssuranceCheck, AssuranceStatus


class AssuranceService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def status(self) -> AssuranceStatus:
        checks = [
            self._check(
                "afe_classification",
                "Active AFE lines have a configured classification",
                self._count(
                    select(func.count())
                    .select_from(AfeLine)
                    .where(AfeLine.is_active.is_(True), AfeLine.secondary_category_id.is_(None))
                ),
                "Every active AFE line must point to a user-configured secondary category.",
            ),
            self._check(
                "estimate_line_scope",
                "Estimate rates point to active AFE lines",
                self._estimate_scope_violations(),
                "Every active estimate rate must belong to an active line of the same AFE.",
            ),
            self._check(
                "daily_cost_source",
                "Daily Cost lines retain an AFE or historical catalogue source",
                self._daily_source_violations(),
                "Every Daily Cost charge must be traceable to its configured AFE line.",
            ),
            self._check(
                "daily_cost_totals",
                "Daily Cost totals reconcile to charge lines",
                self._daily_total_violations(),
                "Header totals must equal the sum of their operational and quantity charges.",
            ),
            self._check(
                "daily_activity_scope",
                "Daily Cost activities belong to the same well",
                self._activity_scope_violations(),
                "The day activity used for accountability must be configured for that well.",
            ),
        ]
        return AssuranceStatus(
            status="framework_ready" if all(item.violations == 0 for item in checks) else "failed",
            migration_head="20260825_0027",
            reporting_contract_version="2.0",
            checks=checks,
            blockers=[],
        )

    def _estimate_scope_violations(self) -> int:
        rates = self.session.scalars(
            select(AfeCostEstimateLine).where(AfeCostEstimateLine.is_active.is_(True))
        ).all()
        return sum(
            not rate.afe_line.is_active or rate.afe_line.afe_id != rate.afe_id for rate in rates
        )

    def _daily_source_violations(self) -> int:
        service_count = self._count(
            select(func.count())
            .select_from(DailyCostServiceLine)
            .where(
                DailyCostServiceLine.afe_line_id.is_(None),
                DailyCostServiceLine.service_id.is_(None),
            )
        )
        quantity_count = self._count(
            select(func.count())
            .select_from(DailyCostConsumableLine)
            .where(
                DailyCostConsumableLine.afe_line_id.is_(None),
                DailyCostConsumableLine.consumable_id.is_(None),
            )
        )
        return service_count + quantity_count

    def _daily_total_violations(self) -> int:
        violations = 0
        entries = self.session.scalars(
            select(DailyCostEntry).where(DailyCostEntry.is_active.is_(True))
        ).all()
        for entry in entries:
            operational = sum((Decimal(line.amount) for line in entry.services), Decimal("0"))
            quantity = sum((Decimal(line.amount) for line in entry.consumables), Decimal("0"))
            if (
                operational != Decimal(entry.total_services_cost)
                or quantity != Decimal(entry.total_consumables_cost)
                or operational + quantity != Decimal(entry.total_daily_cost)
            ):
                violations += 1
        return violations

    def _activity_scope_violations(self) -> int:
        entries = self.session.scalars(
            select(DailyCostEntry).where(DailyCostEntry.is_active.is_(True))
        ).all()
        return sum(
            entry.sub_activity is None or entry.sub_activity.well_id != entry.well_id
            for entry in entries
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
