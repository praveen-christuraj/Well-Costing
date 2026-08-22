"""Daily cost entry processing, rate calculations, and AFE comparative analytics."""

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessValidationError, ConflictError, NotFoundError
from app.models.afe import Afe, Well
from app.models.daily_cost import (
    DailyCostConsumableLine,
    DailyCostEntry,
    DailyCostServiceLine,
)
from app.models.master_data import CatalogItem, CostCode, HoleSection, Unit, Vendor
from app.models.well_costing import WellServiceRate, WellTangibleRate
from app.schemas.daily_cost import (
    ConsumableBreakdownItem,
    DailyCostAnalyticsRead,
    DailyCostConsumableLineRead,
    DailyCostEntryCreate,
    DailyCostEntryRead,
    DailyCostEntryUpdate,
    DailyCostServiceLineRead,
    DailyTrendPoint,
    ReferenceConsumableRate,
    ReferenceServiceRate,
    ServiceBreakdownItem,
)
from app.services.audit import log_entity_action


class DailyCostService:
    def __init__(self, session: Session, actor_id: UUID) -> None:
        self.session, self.actor_id = session, actor_id

    def list_entries(self, well_id: UUID) -> list[DailyCostEntryRead]:
        well = self.session.get(Well, well_id)
        if not well or not well.is_active:
            raise NotFoundError("Well not found")
        entries = self.session.scalars(
            select(DailyCostEntry)
            .where(DailyCostEntry.well_id == well_id, DailyCostEntry.is_active.is_(True))
            .order_by(DailyCostEntry.entry_date.desc())
        ).all()
        return [self._read_entry(e) for e in entries]

    def get_entry(self, well_id: UUID, entry_date: date) -> DailyCostEntryRead | None:
        entry = self.session.scalar(
            select(DailyCostEntry).where(
                DailyCostEntry.well_id == well_id,
                DailyCostEntry.entry_date == entry_date,
                DailyCostEntry.is_active.is_(True),
            )
        )
        return self._read_entry(entry) if entry else None

    def save_entry(self, well_id: UUID, payload: DailyCostEntryCreate) -> DailyCostEntryRead:
        well = self.session.get(Well, well_id)
        if not well or not well.is_active:
            raise NotFoundError("Well not found")

        afe_id = payload.afe_id
        if not afe_id:
            # Pick active/submitted AFE for the well, or latest draft AFE
            active_afe = self.session.scalar(
                select(Afe)
                .where(Afe.well_id == well_id, Afe.is_active.is_(True))
                .order_by(Afe.status.desc(), Afe.revision_number.desc())
            )
            afe_id = active_afe.id if active_afe else None

        entry = self.session.scalar(
            select(DailyCostEntry).where(
                DailyCostEntry.well_id == well_id,
                DailyCostEntry.entry_date == payload.entry_date,
            )
        )

        if not entry:
            created = True
            entry = DailyCostEntry(
                well_id=well_id,
                afe_id=afe_id,
                entry_date=payload.entry_date,
                hole_section_id=payload.hole_section_id,
                phase=payload.phase,
                current_depth=payload.current_depth,
                daily_progress=payload.daily_progress,
                operational_summary=payload.operational_summary,
                created_by=self.actor_id,
                updated_by=self.actor_id,
            )
            self.session.add(entry)
            self.session.flush()
        else:
            created = False
            entry.afe_id = afe_id
            entry.hole_section_id = payload.hole_section_id
            entry.phase = payload.phase
            entry.current_depth = payload.current_depth
            entry.daily_progress = payload.daily_progress
            entry.operational_summary = payload.operational_summary
            entry.is_active = True
            entry.updated_by = self.actor_id

            # Clear existing lines for this entry
            self.session.execute(
                delete(DailyCostServiceLine).where(DailyCostServiceLine.daily_cost_entry_id == entry.id)
            )
            self.session.execute(
                delete(DailyCostConsumableLine).where(DailyCostConsumableLine.daily_cost_entry_id == entry.id)
            )
            self.session.flush()

        total_services = Decimal("0")
        for s_input in payload.services:
            hours = Decimal(str(s_input.service_hours))
            if hours < 0 or hours > 24:
                raise BusinessValidationError("Service hours must be between 0 and 24")
            operating_days = hours / Decimal("24.0")
            rate = Decimal(str(s_input.unit_rate))
            if s_input.rate_basis == "daily":
                line_amount = operating_days * rate
            else:
                line_amount = rate
            total_services += line_amount

            s_line = DailyCostServiceLine(
                daily_cost_entry_id=entry.id,
                service_id=s_input.service_id,
                cost_code_id=s_input.cost_code_id,
                vendor_id=s_input.vendor_id,
                hole_section_id=s_input.hole_section_id or payload.hole_section_id,
                service_hours=hours,
                operating_days=operating_days,
                rate_basis=s_input.rate_basis,
                unit_rate=rate,
                amount=line_amount,
                remarks=s_input.remarks,
                created_by=self.actor_id,
                updated_by=self.actor_id,
            )
            self.session.add(s_line)

        total_consumables = Decimal("0")
        for c_input in payload.consumables:
            qty = Decimal(str(c_input.quantity))
            rate = Decimal(str(c_input.unit_rate))
            line_amount = qty * rate
            total_consumables += line_amount

            c_line = DailyCostConsumableLine(
                daily_cost_entry_id=entry.id,
                consumable_id=c_input.consumable_id,
                cost_code_id=c_input.cost_code_id,
                vendor_id=c_input.vendor_id,
                quantity=qty,
                unit_id=c_input.unit_id,
                unit_rate=rate,
                amount=line_amount,
                remarks=c_input.remarks,
                created_by=self.actor_id,
                updated_by=self.actor_id,
            )
            self.session.add(c_line)

        entry.total_services_cost = total_services
        entry.total_consumables_cost = total_consumables
        entry.total_daily_cost = total_services + total_consumables
        self.session.flush()

        log_entity_action(
            self.session,
            self.actor_id,
            "create" if created else "update",
            "daily_cost_entry",
            entity_id=entry.id,
            entity_code=str(entry.entry_date),
            details={"well_id": str(well_id), "total": str(entry.total_daily_cost)},
        )
        self._recompute_cumulative_costs(well_id)
        self.session.commit()
        self.session.refresh(entry)
        return self._read_entry(entry)

    def delete_entry(self, well_id: UUID, entry_id: UUID) -> None:
        """Soft-delete a daily cost entry and recompute the cumulative costs."""
        entry = self.session.get(DailyCostEntry, entry_id)
        if not entry or entry.well_id != well_id:
            raise NotFoundError("Daily cost entry not found")
        if not entry.is_active:
            raise BusinessValidationError("Daily cost entry is already deleted")
        entry.is_active = False
        entry.updated_by = self.actor_id
        self.session.flush()
        log_entity_action(
            self.session,
            self.actor_id,
            "soft_delete",
            "daily_cost_entry",
            entity_id=entry.id,
            entity_code=str(entry.entry_date),
            details={"well_id": str(well_id)},
        )
        self._recompute_cumulative_costs(well_id)
        self.session.commit()

    def recover_entry(self, well_id: UUID, entry_id: UUID) -> DailyCostEntryRead:
        """Recover a soft-deleted daily cost entry."""
        entry = self.session.get(DailyCostEntry, entry_id)
        if not entry or entry.well_id != well_id:
            raise NotFoundError("Daily cost entry not found")
        if entry.is_active:
            raise BusinessValidationError("Daily cost entry is not deleted and cannot be recovered")
        existing = self.session.scalar(
            select(DailyCostEntry).where(
                DailyCostEntry.well_id == well_id,
                DailyCostEntry.entry_date == entry.entry_date,
                DailyCostEntry.is_active.is_(True),
                DailyCostEntry.id != entry.id,
            )
        )
        if existing:
            raise ConflictError(
                "An active entry for this date already exists. Delete it before recovering."
            )
        entry.is_active = True
        entry.updated_by = self.actor_id
        self.session.flush()
        log_entity_action(
            self.session,
            self.actor_id,
            "recover",
            "daily_cost_entry",
            entity_id=entry.id,
            entity_code=str(entry.entry_date),
            details={"well_id": str(well_id)},
        )
        self._recompute_cumulative_costs(well_id)
        self.session.commit()
        self.session.refresh(entry)
        return self._read_entry(entry)

    def get_reference_rates(self, well_id: UUID) -> dict[str, list[Any]]:
        well = self.session.get(Well, well_id)
        if not well or not well.is_active:
            raise NotFoundError("Well not found")

        # 1. Services with well rates or catalog items
        well_service_rates = self.session.scalars(
            select(WellServiceRate)
            .where(WellServiceRate.well_id == well_id, WellServiceRate.is_active.is_(True))
        ).all()
        well_rate_by_svc = {r.service_id: r for r in well_service_rates}

        services = self.session.scalars(
            select(CatalogItem)
            .where(CatalogItem.item_type == "service", CatalogItem.is_active.is_(True))
            .order_by(CatalogItem.code)
        ).all()

        ref_services: list[ReferenceServiceRate] = []
        for s in services:
            wr = well_rate_by_svc.get(s.id)
            op_rate = wr.operating_rate if wr else Decimal("0")
            rate_basis = wr.rate_basis if wr else (getattr(s, "rate_basis", None) or "daily")
            cost_code_id = s.cost_code_id
            cost_code = s.cost_code.code if s.cost_code else "UNKNOWN"
            unit_code = wr.unit.code if wr and wr.unit else (s.default_unit.code if s.default_unit else "DAY")
            ref_services.append(
                ReferenceServiceRate(
                    service_id=s.id,
                    service_code=s.code,
                    service_name=s.name,
                    cost_code_id=cost_code_id,
                    cost_code=cost_code,
                    vendor_id=wr.vendor_id if wr else None,
                    vendor_name=wr.vendor.name if wr and wr.vendor else None,
                    rate_basis=rate_basis,
                    operating_rate=op_rate,
                    unit_code=unit_code,
                )
            )

        # 2. Consumables (mud chemicals, cement additives, materials)
        consumable_types = {"mud_chemical", "cement_additive", "material", "tangible"}
        consumables = self.session.scalars(
            select(CatalogItem)
            .where(CatalogItem.item_type.in_(consumable_types), CatalogItem.is_active.is_(True))
            .order_by(CatalogItem.item_type, CatalogItem.code)
        ).all()

        well_tangibles = self.session.scalars(
            select(WellTangibleRate)
            .where(WellTangibleRate.well_id == well_id, WellTangibleRate.is_active.is_(True))
        ).all()
        well_tangible_map = {t.tangible_id: t for t in well_tangibles}

        ref_consumables: list[ReferenceConsumableRate] = []
        for c in consumables:
            wt = well_tangible_map.get(c.id)
            unit_rate = wt.unit_rate if wt else Decimal("0")
            unit_id = c.default_unit_id
            unit_code = c.default_unit.code if c.default_unit else "EA"
            cost_code_id = c.cost_code_id
            cost_code = c.cost_code.code if c.cost_code else "UNKNOWN"
            ref_consumables.append(
                ReferenceConsumableRate(
                    consumable_id=c.id,
                    consumable_code=c.code,
                    consumable_name=c.name,
                    item_type=c.item_type,
                    cost_code_id=cost_code_id,
                    cost_code=cost_code,
                    unit_id=unit_id,
                    unit_code=unit_code,
                    unit_rate=unit_rate,
                )
            )

        return {
            "services": [s.model_dump() for s in ref_services],
            "consumables": [c.model_dump() for c in ref_consumables],
        }

    def get_analytics(self, well_id: UUID) -> DailyCostAnalyticsRead:
        well = self.session.get(Well, well_id)
        if not well or not well.is_active:
            raise NotFoundError("Well not found")

        afe = self.session.scalar(
            select(Afe)
            .where(Afe.well_id == well_id, Afe.is_active.is_(True))
            .order_by(Afe.status.desc(), Afe.revision_number.desc())
        )

        afe_budget = Decimal("0")
        total_planned_days = Decimal("0")
        if afe:
            afe_budget = afe.budget_amount if afe.budget_amount > 0 else Decimal("0")
            total_planned_days = afe.total_planned_days if afe.total_planned_days > 0 else Decimal("0")

        entries = self.session.scalars(
            select(DailyCostEntry)
            .where(DailyCostEntry.well_id == well_id, DailyCostEntry.is_active.is_(True))
            .order_by(DailyCostEntry.entry_date.asc())
        ).all()

        cumulative_cost = Decimal("0")
        trend_all: list[DailyTrendPoint] = []
        services_dict: dict[UUID, dict[str, Any]] = {}
        consumables_dict: dict[UUID, dict[str, Any]] = {}

        for e in entries:
            cumulative_cost += e.total_daily_cost
            trend_all.append(
                DailyTrendPoint(
                    entry_date=e.entry_date,
                    daily_cost=e.total_daily_cost,
                    cumulative_cost=cumulative_cost,
                    services_cost=e.total_services_cost,
                    consumables_cost=e.total_consumables_cost,
                    phase=e.phase,
                    current_depth=e.current_depth,
                )
            )
            for s in e.services:
                if s.service_id not in services_dict:
                    services_dict[s.service_id] = {
                        "service_id": s.service_id,
                        "service_code": s.service.code if s.service else "SVC",
                        "service_name": s.service.name if s.service else "Service",
                        "total_hours": Decimal("0"),
                        "total_days": Decimal("0"),
                        "total_cost": Decimal("0"),
                    }
                services_dict[s.service_id]["total_hours"] += s.service_hours
                services_dict[s.service_id]["total_days"] += s.operating_days
                services_dict[s.service_id]["total_cost"] += s.amount

            for c in e.consumables:
                if c.consumable_id not in consumables_dict:
                    consumables_dict[c.consumable_id] = {
                        "consumable_id": c.consumable_id,
                        "consumable_code": c.consumable.code if c.consumable else "CHEM",
                        "consumable_name": c.consumable.name if c.consumable else "Consumable",
                        "unit_code": c.unit.code if c.unit else "UOM",
                        "total_quantity": Decimal("0"),
                        "total_cost": Decimal("0"),
                    }
                consumables_dict[c.consumable_id]["total_quantity"] += c.quantity
                consumables_dict[c.consumable_id]["total_cost"] += c.amount

        days_elapsed = len(entries)
        burn_rate = (cumulative_cost / Decimal(str(days_elapsed))) if days_elapsed > 0 else Decimal("0")
        remaining_days = max(Decimal("0"), total_planned_days - Decimal(str(days_elapsed)))
        forecast_cost = cumulative_cost + (remaining_days * burn_rate)
        balance = afe_budget - cumulative_cost
        variance = afe_budget - forecast_cost

        # Services breakdown list with percentage
        tot_svc = sum((item["total_cost"] for item in services_dict.values()), Decimal("0"))
        services_breakdown = [
            ServiceBreakdownItem(
                service_id=v["service_id"],
                service_code=v["service_code"],
                service_name=v["service_name"],
                total_hours=v["total_hours"],
                total_days=v["total_days"],
                total_cost=v["total_cost"],
                percentage=((v["total_cost"] / tot_svc) * 100) if tot_svc > 0 else Decimal("0"),
            )
            for v in sorted(services_dict.values(), key=lambda x: x["total_cost"], reverse=True)
        ]

        # Consumables breakdown list with percentage
        tot_con = sum((item["total_cost"] for item in consumables_dict.values()), Decimal("0"))
        consumables_breakdown = [
            ConsumableBreakdownItem(
                consumable_id=v["consumable_id"],
                consumable_code=v["consumable_code"],
                consumable_name=v["consumable_name"],
                unit_code=v["unit_code"],
                total_quantity=v["total_quantity"],
                total_cost=v["total_cost"],
                percentage=((v["total_cost"] / tot_con) * 100) if tot_con > 0 else Decimal("0"),
            )
            for v in sorted(consumables_dict.values(), key=lambda x: x["total_cost"], reverse=True)
        ]

        return DailyCostAnalyticsRead(
            well_id=well_id,
            well_code=well.code,
            afe_id=afe.id if afe else None,
            afe_code=afe.code if afe else None,
            afe_budget=afe_budget,
            total_planned_days=total_planned_days,
            cumulative_actual_cost=cumulative_cost,
            balance_amount=balance,
            days_elapsed=days_elapsed,
            burn_rate_daily_avg=burn_rate,
            remaining_planned_days=remaining_days,
            forecast_at_end_of_well=forecast_cost,
            variance_to_afe=variance,
            trend_last_5_days=trend_all[-5:],
            trend_last_7_days=trend_all[-7:],
            trend_all_days=trend_all,
            services_breakdown=services_breakdown,
            consumables_breakdown=consumables_breakdown,
        )

    def _recompute_cumulative_costs(self, well_id: UUID) -> None:
        entries = self.session.scalars(
            select(DailyCostEntry)
            .where(DailyCostEntry.well_id == well_id, DailyCostEntry.is_active.is_(True))
            .order_by(DailyCostEntry.entry_date.asc())
        ).all()
        running_total = Decimal("0")
        for e in entries:
            running_total += e.total_daily_cost
            e.cumulative_cost = running_total

    @staticmethod
    def _read_entry(entry: DailyCostEntry) -> DailyCostEntryRead:
        services_read = [
            DailyCostServiceLineRead(
                id=s.id,
                daily_cost_entry_id=s.daily_cost_entry_id,
                service_id=s.service_id,
                service_code=s.service.code if s.service else None,
                service_name=s.service.name if s.service else None,
                cost_code_id=s.cost_code_id,
                cost_code=s.cost_code.code if s.cost_code else None,
                vendor_id=s.vendor_id,
                vendor_name=s.vendor.name if s.vendor else None,
                hole_section_id=s.hole_section_id,
                hole_section_code=s.hole_section.code if s.hole_section else None,
                service_hours=s.service_hours,
                operating_days=s.operating_days,
                rate_basis=s.rate_basis,
                unit_rate=s.unit_rate,
                amount=s.amount,
                remarks=s.remarks,
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
            for s in (entry.services or [])
        ]
        consumables_read = [
            DailyCostConsumableLineRead(
                id=c.id,
                daily_cost_entry_id=c.daily_cost_entry_id,
                consumable_id=c.consumable_id,
                consumable_code=c.consumable.code if c.consumable else None,
                consumable_name=c.consumable.name if c.consumable else None,
                cost_code_id=c.cost_code_id,
                cost_code=c.cost_code.code if c.cost_code else None,
                vendor_id=c.vendor_id,
                vendor_name=c.vendor.name if c.vendor else None,
                quantity=c.quantity,
                unit_id=c.unit_id,
                unit_code=c.unit.code if c.unit else None,
                unit_rate=c.unit_rate,
                amount=c.amount,
                remarks=c.remarks,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
            for c in (entry.consumables or [])
        ]
        return DailyCostEntryRead(
            id=entry.id,
            well_id=entry.well_id,
            well_code=entry.well.code if entry.well else None,
            afe_id=entry.afe_id,
            afe_code=entry.afe.code if entry.afe else None,
            entry_date=entry.entry_date,
            hole_section_id=entry.hole_section_id,
            hole_section_code=entry.hole_section.code if entry.hole_section else None,
            phase=entry.phase,
            current_depth=entry.current_depth,
            daily_progress=entry.daily_progress,
            operational_summary=entry.operational_summary,
            total_services_cost=entry.total_services_cost,
            total_consumables_cost=entry.total_consumables_cost,
            total_daily_cost=entry.total_daily_cost,
            cumulative_cost=entry.cumulative_cost,
            is_active=entry.is_active,
            services=services_read,
            consumables=consumables_read,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
        )
