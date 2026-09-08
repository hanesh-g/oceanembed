import pytest
from httpx import AsyncClient
from fastapi import FastAPI

@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient, app: FastAPI):
    """Test the /v1/ocean/health endpoint returns 200 OK and valid status."""
    response = await client.get("/v1/ocean/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "live_week" in data

@pytest.mark.asyncio
async def test_field_json_endpoint(client: AsyncClient, app: FastAPI):
    """Test the /v1/ocean/field_json endpoint returns vectorized data."""
    response = await client.get("/v1/ocean/field_json?variable=temp&depth=0")
    assert response.status_code == 200
    data = response.json()
    assert "variable" in data
    assert data["variable"] == "temp"
    assert "data" in data

@pytest.mark.asyncio
async def test_argo_floats_endpoint(client: AsyncClient, app: FastAPI):
    """Test the /v1/ocean/argo_floats endpoint returns a list of floats."""
    response = await client.get("/v1/ocean/argo_floats")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

@pytest.mark.asyncio
async def test_profile_endpoint(client: AsyncClient, app: FastAPI):
    """Test the /v1/ocean/profile endpoint returns 15-depth profile data."""
    response = await client.get("/v1/ocean/profile?lat=0.0&lon=0.0")
    assert response.status_code == 200
    data = response.json()
    assert "depths" in data
    assert "values" in data
    assert "nearest_argo" in data
