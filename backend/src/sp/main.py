from __future__ import annotations

import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from sp.api import auth_routes, config_routes, health, radar_routes
from sp.core.logging import (
    bind_request_context,
    clear_request_context,
    configure_logging,
    get_logger,
)
from sp.core.settings import get_settings

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(title="Sistema de Propuestas - API")

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
    app.include_router(radar_routes.router)

    return app


app = create_app()
