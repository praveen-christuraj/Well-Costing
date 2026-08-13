"""FastAPI application factory and ASGI entry point."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""

    runtime_settings = settings or get_settings()
    configure_logging(runtime_settings.LOG_LEVEL)
    logger = logging.getLogger("app")

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
        logger.info(
            "Application started",
            extra={
                "environment": runtime_settings.ENVIRONMENT,
                "version": runtime_settings.APP_VERSION,
            },
        )
        yield
        logger.info("Application stopped")

    expose_api_docs = runtime_settings.ENVIRONMENT in {"development", "test"}
    application = FastAPI(
        title="Drilling Costing API",
        version=runtime_settings.APP_VERSION,
        docs_url="/docs" if expose_api_docs else None,
        redoc_url="/redoc" if expose_api_docs else None,
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=runtime_settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    register_exception_handlers(application, runtime_settings)
    application.include_router(api_router, prefix=runtime_settings.API_V1_PREFIX)
    return application


app = create_app()
