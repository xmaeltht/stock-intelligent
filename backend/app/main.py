import logging
from contextlib import asynccontextmanager
from threading import Event

from fastapi import FastAPI, HTTPException, status
from sqlalchemy import text

from app.api.router import api_router
from app.core.config import get_settings
from app.db.session import engine

logger = logging.getLogger("stock-intelligence")
settings = get_settings()

_worker_stop = Event()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Embed the analyzer loops in the always-on backend so scanning runs non-stop
    # (live price loop + optional deep fundamental loop) without a separate pod.
    threads = []
    if settings.backend_run_live_loop or settings.backend_run_deep_loop:
        try:
            from app.jobs.continuous_analyzer import start_background_workers

            threads = start_background_workers(
                _worker_stop,
                run_deep=settings.backend_run_deep_loop,
                run_live=settings.backend_run_live_loop,
            )
        except Exception:  # noqa: BLE001 - never let workers block API startup
            logger.exception("failed to start background analyzer workers")
    try:
        yield
    finally:
        _worker_stop.set()
        for thread in threads:
            thread.join(timeout=5)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)
app.include_router(api_router, prefix="/api/v1")


@app.get("/health/live", tags=["health"])
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
def readiness() -> dict[str, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database unavailable",
        ) from exc
    return {"status": "ok"}

