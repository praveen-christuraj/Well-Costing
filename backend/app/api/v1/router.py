"""Version 1 API route aggregation."""

from fastapi import APIRouter

from app.api.v1.routes import (
    afe,
    audit_logs,
    auth,
    catalogue_config,
    catalogue_consumables,
    catalogue_drill_bits,
    catalogue_services,
    catalogue_tangibles,
    health,
    master_data,
    rig_well,
    vendor_po,
    well_sub_activity,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
# Catalogue routes (Services / Consumables / Tangibles + dropdown config).
api_router.include_router(catalogue_config.router)
api_router.include_router(catalogue_services.router)
api_router.include_router(catalogue_consumables.router)
api_router.include_router(catalogue_drill_bits.router)
api_router.include_router(catalogue_tangibles.router)
# Vendor/PO routes must be registered before generic master-data {module} routes
# so that static paths like /vendors/export take precedence over /{module}/export
api_router.include_router(vendor_po.router)
api_router.include_router(master_data.router)
api_router.include_router(rig_well.router)
# AFE routes own /afe/... (AFE header + AFE cost estimation).
api_router.include_router(afe.router)
# Well Sub Activities owns /well-sub-activities/... (completely well scoped).
api_router.include_router(well_sub_activity.router)
api_router.include_router(audit_logs.router)
