"""
Ocean module router — aggregates all /v1/ocean/* sub-routers.

Included by the v1 API router in backend/src/interfaces/api/v1/__init__.py.
"""

from fastapi import APIRouter

from .field import router as field_router
from .profile import router as profile_router
from .health import router as health_router
from .argo import router as argo_router
from .saliency import router as saliency_router
from .sampling import router as sampling_router
from .benchmark import router as benchmark_router

ocean_router = APIRouter(prefix="/ocean")

ocean_router.include_router(field_router)
ocean_router.include_router(profile_router)
ocean_router.include_router(health_router)
ocean_router.include_router(argo_router)
ocean_router.include_router(saliency_router)
ocean_router.include_router(sampling_router)
ocean_router.include_router(benchmark_router)
