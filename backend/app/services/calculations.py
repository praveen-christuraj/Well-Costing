"""Map persisted estimates to the pure costing domain and audit every attempt."""

from dataclasses import asdict
from datetime import UTC, date, datetime
from typing import Any, cast
from uuid import UUID

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRulePendingError, NotFoundError
from app.domain.costing.calculations import calculate_estimate
from app.domain.costing.types import (
    AssumptionInput,
    EstimateInput,
    EstimateLineInput,
    EstimateResult,
    RateInput,
)
from app.models.calculations import EstimateCalculation
from app.models.estimates import CostEstimate, EstimateVersion
from app.schemas.calculations import CalculationRunRead, EstimateCalculationResults

ENGINE_VERSION = "0.1.0"
RULE_SET_VERSION = "pending-full-chain"
PENDING_RULES = [
    "effective quantity and override precedence",
    "automatic effective-dated rate resolution and vendor precedence",
    "currency conversion and exchange-rate basis",
    "contingency application basis and ordering",
    "escalation application basis and timing",
    "rounding precision and sequence",
    "category subtotal and grand-total treatment",
]


class EstimateCalculationService:
    def __init__(self, session: Session, actor_id: UUID) -> None:
        self.session, self.actor_id = session, actor_id

    def calculate(
        self, estimate_id: UUID, version_id: UUID | None = None
    ) -> EstimateCalculationResults:
        estimate = self.session.get(CostEstimate, estimate_id)
        if estimate is None:
            raise NotFoundError("Estimate not found")
        version = self._version(estimate, version_id)
        domain_input = self._input(estimate, version)
        input_snapshot = jsonable_encoder(asdict(domain_input))
        run = EstimateCalculation(
            estimate_version_id=version.id,
            engine_version=ENGINE_VERSION,
            rule_set_version=RULE_SET_VERSION,
            status="started",
            input_snapshot=input_snapshot,
            created_by=self.actor_id,
            updated_by=self.actor_id,
        )
        self.session.add(run)
        self.session.flush()
        try:
            result = calculate_estimate(domain_input)
        except NotImplementedError as exc:
            run.status = "blocked"
            run.message = str(exc)
            run.updated_by = self.actor_id
            self.session.commit()
            raise BusinessRulePendingError(
                "Estimate calculation is blocked pending confirmed business rules",
                {
                    "calculation_run_id": str(run.id),
                    "engine_version": ENGINE_VERSION,
                    "rule_set_version": RULE_SET_VERSION,
                    "pending_rules": PENDING_RULES,
                },
            ) from exc
        self._persist(version, run, result)
        self.session.commit()
        return self.results(estimate_id, version.id)

    def results(
        self, estimate_id: UUID, version_id: UUID | None = None
    ) -> EstimateCalculationResults:
        estimate = self.session.get(CostEstimate, estimate_id)
        if estimate is None:
            raise NotFoundError("Estimate not found")
        version = self._version(estimate, version_id)
        runs = list(
            self.session.scalars(
                select(EstimateCalculation)
                .where(EstimateCalculation.estimate_version_id == version.id)
                .order_by(EstimateCalculation.created_at.desc())
            ).all()
        )
        completed = next((run for run in runs if run.status == "completed"), None)
        output = completed.output_snapshot if completed and completed.output_snapshot else {}
        return EstimateCalculationResults(
            estimate_id=estimate.id,
            estimate_version_id=version.id,
            version_number=version.version_number,
            currency_code=estimate.currency.code,
            base_total=version.base_total,
            contingency_total=version.contingency_total,
            escalation_total=version.escalation_total,
            grand_total=version.grand_total,
            calculation_status=runs[0].status if runs else "not_calculated",
            line_results=cast(list[dict[str, Any]], output.get("lines", [])),
            category_results=cast(list[dict[str, Any]], output.get("categories", [])),
            calculation_runs=[CalculationRunRead.model_validate(run) for run in runs],
            pending_rules=PENDING_RULES if completed is None else [],
        )

    @staticmethod
    def _version(estimate: CostEstimate, version_id: UUID | None) -> EstimateVersion:
        if version_id is not None:
            version = next((item for item in estimate.versions if item.id == version_id), None)
        else:
            version = next(
                (
                    item
                    for item in estimate.versions
                    if item.version_number == estimate.current_version_number
                ),
                None,
            )
        if version is None:
            raise NotFoundError("Estimate version not found")
        return version

    @staticmethod
    def _input(estimate: CostEstimate, version: EstimateVersion) -> EstimateInput:
        lines: list[EstimateLineInput] = []
        for item in version.items:
            rate = None
            if item.rate is not None:
                rate = RateInput(
                    amount=item.rate.amount,
                    currency_code=item.rate.currency.code,
                    unit_code=item.rate.unit.code,
                    effective_from=item.rate.effective_from,
                    effective_to=item.rate.effective_to,
                )
            category = item.catalog_item.cost_category
            lines.append(
                EstimateLineInput(
                    line_id=str(item.id),
                    item_code=item.catalog_item.code,
                    item_type=item.catalog_item.item_type,
                    cost_code=item.cost_code.code,
                    cost_category_code=category.code if category else None,
                    quantity=item.quantity,
                    quantity_unit_code=item.unit.code,
                    rate=rate,
                    vendor_code=item.vendor.code if item.vendor else None,
                )
            )
        assumptions = tuple(
            AssumptionInput(
                cost_category_code=(
                    assumption.cost_category.code if assumption.cost_category else None
                ),
                contingency_percent=assumption.contingency_percent,
                escalation_percent=assumption.escalation_percent,
            )
            for assumption in version.assumptions
        )
        return EstimateInput(
            estimate_id=str(estimate.id),
            version_id=str(version.id),
            currency_code=estimate.currency.code,
            calculation_date=date.today(),
            lines=tuple(lines),
            assumptions=assumptions,
        )

    def _persist(
        self, version: EstimateVersion, run: EstimateCalculation, result: EstimateResult
    ) -> None:
        by_id = {str(item.id): item for item in version.items}
        for line in result.lines:
            item = by_id[line.line_id]
            item.base_cost = line.base_cost
            item.contingency_cost = line.contingency_cost
            item.escalation_cost = line.escalation_cost
            item.total_cost = line.total_cost
            item.updated_by = self.actor_id
        version.base_total = result.base_total
        version.contingency_total = result.contingency_total
        version.escalation_total = result.escalation_total
        version.grand_total = result.grand_total
        version.updated_by = self.actor_id
        run.status = "completed"
        run.output_snapshot = jsonable_encoder(asdict(result))
        run.message = f"Calculation completed at {datetime.now(UTC).isoformat()}"
        run.updated_by = self.actor_id
