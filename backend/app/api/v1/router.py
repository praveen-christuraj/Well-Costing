"""Version 1 API route aggregation."""

from fastapi import APIRouter

from app.api.v1.routes import (
    afe,
    assurance,
    auth,
    calculations,
    cost_control,
    enterprise_config,
    estimates,
    health,
    imports,
    master_data,
    procurement,
    rates,
    reporting,
    requirement_imports,
    requirements,
    well_costing,
    workflow,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(assurance.router)
api_router.include_router(enterprise_config.router)
api_router.include_router(calculations.router)
api_router.include_router(afe.router)
api_router.include_router(workflow.router)
api_router.include_router(cost_control.router)
api_router.include_router(reporting.router)
api_router.include_router(estimates.router)
api_router.include_router(procurement.router)
api_router.include_router(rates.router)
api_router.include_router(master_data.router)
api_router.include_router(imports.router)
api_router.include_router(requirement_imports.router)
api_router.include_router(requirements.router)
api_router.include_router(well_costing.router)
