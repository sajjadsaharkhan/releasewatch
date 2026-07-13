"""Releasewatch FastAPI application entry-point.

Call ``create_app()`` to get a configured FastAPI instance.
The module-level ``app`` is used by uvicorn.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.redis_client import close_redis, init_redis
from app.db.session import close_engine, init_engine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Manage startup and shutdown side-effects."""
    # ── startup ──────────────────────────────────────────────────────────────
    await init_engine()
    await init_redis()

    # Bootstrap admin user if ADMIN_PASSWORD is set and no admin exists yet
    if settings.ADMIN_PASSWORD:
        try:
            from sqlalchemy import select
            from sqlalchemy.ext.asyncio import AsyncSession
            from app.db.session import get_engine
            from app.db.models.user import User, UserRole
            from app.core.auth import get_password_hash

            async with AsyncSession(get_engine()) as db:
                result = await db.execute(select(User).where(User.username == "admin"))
                if result.scalar_one_or_none() is None:
                    admin = User(
                        name="Admin",
                        username="admin",
                        hashed_password=get_password_hash(settings.ADMIN_PASSWORD),
                        role=UserRole.admin,
                        title="System Administrator",
                        is_active=True,
                    )
                    db.add(admin)
                    await db.commit()
                    logger.info("Admin user created (username: admin)")
                else:
                    logger.debug("Admin user already exists — skipping bootstrap")
        except Exception as exc:
            logger.warning("Admin bootstrap failed: %s", exc)

    # Initialize S3 bucket and lifecycle policy
    from app.core.s3 import s3_service
    try:
        s3_service.ensure_bucket_exists()
        s3_service.ensure_lifecycle_policy()
    except Exception as e:
        logging.warning(f"S3 initialization skipped: {e}")

    # Pre-load the local embedding model so the first search request is instant
    async def _warm_embedder() -> None:
        try:
            from sqlalchemy.ext.asyncio import AsyncSession
            from app.db.session import get_engine
            from app.services.search_service import _load_llm_config, _embed_local, _E5_MODELS
            async with AsyncSession(get_engine()) as db:
                cfg = await _load_llm_config(db)
            if cfg.get("provider") == "local":
                prefix = "query: " if cfg["model"] in _E5_MODELS else ""
                await _embed_local(cfg["model"], ["warmup"], prefix=prefix)
                logging.info("Embedding model '%s' loaded and ready.", cfg["model"])
        except Exception as exc:
            logging.warning("Embedding model pre-load skipped: %s", exc)

    asyncio.create_task(_warm_embedder(), name="embedding-warmup")

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
