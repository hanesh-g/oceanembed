from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from .database.session import async_session
from .zarr.resolver import ZarrStoreResolver

# Database
AsyncSessionDep = Annotated[AsyncSession, Depends(async_session)]

# ---------------------------------------------------------------------------
# OceanEmbed — Zarr resolver dependency
# ---------------------------------------------------------------------------

def get_zarr_resolver(request: Request) -> ZarrStoreResolver:
    """Return the application-scoped ZarrStoreResolver.

    The resolver is created once during app startup (see app_factory lifespan or
    the ocean module's setup) and stored on ``app.state.zarr_resolver``.
    Endpoints receive it via ``Depends(get_zarr_resolver)`` and call
    ``await resolver.get_store(week=...)`` to obtain the correct Dataset.
    """
    resolver: ZarrStoreResolver = request.app.state.zarr_resolver
    return resolver

ZarrResolverDep = Annotated[ZarrStoreResolver, Depends(get_zarr_resolver)]
