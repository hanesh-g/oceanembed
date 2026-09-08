from fastapi import APIRouter

from ....modules.ocean.routes import ocean_router

router = APIRouter(prefix="/v1")

# OceanEmbed endpoints — /v1/ocean/*
router.include_router(ocean_router)
