"""Version 1 API route aggregation."""

from fastapi import APIRouter

from app.api.v1.routes import audit_logs, auth, health, master_data

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(master_data.router)
api_router.include_router(audit_logs.router)
