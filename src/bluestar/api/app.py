"""FastAPI application with lifespan and router mounting."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from bluestar.api.routes import admin, health
from bluestar.core.config import AppSettings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize and tear down application resources."""
    settings = AppSettings()
    app.state.settings = settings
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="BlueStar Payroll Processing Platform",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(health.router)
    app.include_router(admin.router, prefix="/admin")
    return app
