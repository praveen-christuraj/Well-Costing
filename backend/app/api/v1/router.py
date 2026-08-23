"""Version 1 API route aggregation."""

from fastapi import APIRouter

from app.api.v1.routes import (
    afe,
    afe_imports,
    afe_snapshots,
    assurance,
    audit,
    auth,
    calculations,
    cost_control,
    daily_cost,
    enterprise_config,
    estimates,
    health,
    imports,
    master_data,
    procurement,
    rates,
    reference,
    reporting,
    well_activities,
    well_costing,
    workflow,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(assurance.router)
api_router.include_router(enterprise_config.router)
api_router.include_router(calculations.router)
api_router.include_router(afe_snapshots.router)
api_router.include_router(workflow.router)
api_router.include_router(cost_control.router)
api_router.include_router(reporting.router)
api_router.include_router(estimates.router)
api_router.include_router(procurement.router)
api_router.include_router(rates.router)
api_router.include_router(reference.router)
api_router.include_router(master_data.router)
api_router.include_router(imports.router)
api_router.include_router(afe_imports.router)
api_router.include_router(afe.router)
api_router.include_router(well_costing.router)
api_router.include_router(well_activities.router)
api_router.include_router(daily_cost.router)
api_router.include_router(audit.router)
