from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from sp.api import auth_routes, config_routes, credentials_routes, health, radar_routes
from sp.core.logging import (
    bind_request_context,
    clear_request_context,
    configure_logging,
    get_logger,
)
from sp.core.settings import get_settings
from sp.jobs.app import app as procrastinate_app

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    # `run_radar_task.defer(...)` (radar_routes, "Ejecutar ahora") necesita el conector de
    # Procrastinate abierto; sin esto falla con `AppNotOpen` en cuanto un administrador lo usa
    # (encontrado al probar la carga inicial completa del radar, /p4-radar segunda revision).
    await procrastinate_app.open_async()
    try:
        yield
    finally:
        await procrastinate_app.close_async()


def create_app() -> FastAPI:
    app = FastAPI(title="Sistema de Propuestas - API", lifespan=_lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        bind_request_context(request_id=request_id, path=request.url.path, method=request.method)
        try:
            response = await call_next(request)
        finally:
            clear_request_context()
        response.headers["x-request-id"] = request_id
        return response

    app.include_router(health.router)
    app.include_router(auth_routes.router)
    app.include_router(config_routes.router)
    app.include_router(credentials_routes.router)
    app.include_router(radar_routes.router)

    return app


app = create_app()
