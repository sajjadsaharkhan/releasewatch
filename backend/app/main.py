"""Releasewatch FastAPI application entry-point.

Call ``create_app()`` to get a configured FastAPI instance.
The module-level ``app`` is used by uvicorn.
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.redis_client import close_redis, init_redis
from app.db.session import close_engine, init_engine


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Manage startup and shutdown side-effects."""
    # ── startup ──────────────────────────────────────────────────────────────
    await init_engine()
    await init_redis()

    yield  # application is now running

    # ── shutdown ──────────────────────────────────────────────────────────────
    await close_redis()
    await close_engine()


def create_app() -> FastAPI:
    """Construct and configure the FastAPI application."""
    application = FastAPI(
        title="Releasewatch API",
        description="QA release-tracking platform — issues, regressions, team inbox.",
        version=settings.APP_VERSION,
        docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
        openapi_url="/openapi.json" if settings.ENVIRONMENT != "production" else None,
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ───────────────────────────────────────────────────────────────
    from app.api.v1.router import api_router  # local import avoids circular deps

    application.include_router(api_router, prefix="/api/v1")

    # ── Health check ──────────────────────────────────────────────────────────
    @application.get("/health", tags=["health"], summary="Liveness / readiness probe")
    async def health_check() -> dict:
        """Return service health including DB and Redis reachability."""
        from app.core.redis_client import get_redis_raw
        from app.db.session import get_engine

        db_ok = False
        redis_ok = False

        try:
            engine = get_engine()
            async with engine.connect() as conn:
                await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
            db_ok = True
        except Exception:
            pass

        try:
            r = await get_redis_raw()
            await r.ping()
            redis_ok = True
        except Exception:
            pass

        return {
            "status": "ok" if (db_ok and redis_ok) else "degraded",
            "version": settings.APP_VERSION,
            "db": "ok" if db_ok else "error",
            "redis": "ok" if redis_ok else "error",
        }

    return application


app = create_app()
