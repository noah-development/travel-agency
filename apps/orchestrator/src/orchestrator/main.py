from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from orchestrator.api import health, trips
from orchestrator.config import get_settings
from orchestrator.logging import RequestContextMiddleware, configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()  # fails fast (RuntimeError) before serving traffic
    configure_logging(settings)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="orchestrator", lifespan=lifespan)
    app.add_middleware(RequestContextMiddleware)
    app.include_router(health.router)
    app.include_router(trips.router, prefix="/trips", tags=["trips"])
    return app


app = create_app()
