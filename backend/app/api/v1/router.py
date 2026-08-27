"""Version 1 API route aggregation."""

from fastapi import APIRouter

from app.api.v1.routes import audit_logs, auth, health, master_data, vendor_po

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
# Vendor/PO routes must be registered before generic master-data {module} routes
# so that static paths like /vendors/export take precedence over /{module}/export
api_router.include_router(vendor_po.router)
api_router.include_router(master_data.router)
api_router.include_router(audit_logs.router)
