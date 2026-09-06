from typing import Annotated, Any

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from .auth.dependencies import get_current_superuser, get_current_user, get_optional_user
from .database.session import async_session
from .zarr.resolver import ZarrStoreResolver

# Database
AsyncSessionDep = Annotated[AsyncSession, Depends(async_session)]

# Users (dict-compat, resolved by crudauth)
CurrentUserDep = Annotated[dict[str, Any], Depends(get_current_user)]
CurrentSuperUserDep = Annotated[dict[str, Any], Depends(get_current_superuser)]
OptionalUserDep = Annotated[dict[str, Any] | None, Depends(get_optional_user)]

# Auth form
OAuth2FormDep = Annotated[OAuth2PasswordRequestForm, Depends()]


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
