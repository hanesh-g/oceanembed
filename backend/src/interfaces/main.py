from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ..infrastructure.app_factory import create_application, lifespan_factory
from ..infrastructure.config.settings import get_settings
from ..infrastructure.security import validate_production_security
from ..interfaces.api import router

settings = get_settings()


@asynccontextmanager
async def lifespan_with_security(app: FastAPI) -> AsyncGenerator[None, None]:
    """Custom lifespan: security validation + OceanEmbed resolver initialisation."""
    if settings.PRODUCTION_SECURITY_VALIDATION_ENABLED:
        validate_production_security(settings)

    # Initialise the Zarr resolver once per process lifetime.
    # Endpoints re-check the symlink periodically via the resolver's TTL —
    # they never cache the resolved path themselves.
    from ..infrastructure.zarr.resolver import ZarrStoreResolver
    import os
    import logging

    # Auto-seed mock data if it doesn't exist
    latest_link = os.path.join(settings.PUBLISHED_ZARR_ROOT, "latest")
    if not os.path.exists(latest_link) and not os.path.islink(latest_link):
        logging.getLogger(__name__).warning("No mock data found. Auto-seeding fake Zarr stores...")
        from ..infrastructure.zarr.fake_data import create_fake_published_layout
        create_fake_published_layout(settings.PUBLISHED_ZARR_ROOT)

    app.state.zarr_resolver = ZarrStoreResolver(
        root=settings.PUBLISHED_ZARR_ROOT,
        recheck_seconds=settings.ZARR_POINTER_RECHECK_SECONDS,
    )

    default_lifespan = lifespan_factory(settings)

    async with default_lifespan(app):
        yield

    # Drop all cached store handles on shutdown.
    app.state.zarr_resolver.invalidate()


app = create_application(
    router=router,
    settings=settings,
    lifespan=lifespan_with_security,
    create_tables_on_startup=None,
    enable_cors=None,
    cors_origins=None,
    enable_docs_in_production=None,
    docs_production_dependency=None,
    enable_gzip=None,
    openapi_prefix=None,
    title="OceanEmbed API",
    summary="Weekly ocean subsurface forecast — pure reader, zero PyTorch",
    description="""
    # OceanEmbed API

    Weekly ensemble ocean subsurface forecasts for the North Indian Ocean.

    * Pre-computed T/S/D26/TCHP/MLD fields at 0.25° resolution, 15 depth levels
    * Calibrated ensemble uncertainty (spread + variance inflation)
    * ARGO float benchmark comparisons via PostGIS nearest-neighbour queries
    * Immutable weekly Zarr storage with atomic symlink publish — no downtime on update
    """,
    version="0.1.0",
    contact={
        "name": "OceanEmbed SIH Team",
    },
    license_info={
        "name": "MIT",
        "identifier": "MIT",
    },
    openapi_tags=None,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

from fastapi.middleware.cors import CORSMiddleware

# CORS: allow the Vite dev server during development.
# In production the frontend is served from the same origin or via nginx,
# so CORS is not needed — but keeping the middleware is harmless.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["GET"],           # API is read-only — no PUT/POST/DELETE
    allow_headers=["*"],
    expose_headers=["X-Shape", "X-Variable", "X-Model-Version", "X-Week"],
)


@app.get("/health", tags=["System"])
async def health_check() -> dict[str, str]:
    """Health check endpoint for monitoring and load balancers."""
    return {"status": "healthy"}
