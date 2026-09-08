import os

# Configure the environment BEFORE importing anything from ``src``: the crudauth
# ``auth`` singleton is constructed at import time and reads ``SESSION_BACKEND``,
# so it must be set to the in-memory backend (no Redis) before that import runs.
os.environ.setdefault("SESSION_BACKEND", "memory")
# Tests run over http (base_url http://test), so the session/CSRF cookies must not be
# Secure-only or httpx won't send them back on follow-up requests.
os.environ.setdefault("SESSION_SECURE_COOKIES", "false")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_tests")
os.environ.setdefault("SQLITE_URI", ":memory:")
os.environ.setdefault("SQLITE_ASYNC_PREFIX", "sqlite+aiosqlite:///")

# Disable the testcontainers Ryuk reaper. Under `pytest -n auto`, each xdist worker
# is a separate process that spins up its own Ryuk container, and Docker Desktop
# chokes mapping all their ports at once ("Port mapping ... port 8080 is not
# available"). Testcontainers' own `with` blocks still clean up on normal exit.
os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

import sys  # noqa: E402
from pathlib import Path  # noqa: E402
from unittest.mock import MagicMock  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
import redis as syncredis  # noqa: E402
import redis.asyncio as aioredis  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from testcontainers.core.docker_client import DockerClient  # noqa: E402

# mypy: disable-error-code="import-untyped"
from testcontainers.postgres import PostgresContainer  # noqa: E402

from src.infrastructure.config.settings import Settings, get_settings  # noqa: E402
from src.infrastructure.database.session import Base, async_session  # noqa: E402
from src.interfaces.main import app  # noqa: E402

TEST_DATABASE_URL = get_settings().DATABASE_URL

backend_dir = Path(__file__).parent.parent
sys.path.append(str(backend_dir))


def is_docker_running() -> bool:
    try:
        DockerClient()
        return True
    except Exception:
        return False


@pytest_asyncio.fixture(scope="session")
async def pg_container():
    """Create a PostgreSQL container for testing."""
    if not is_docker_running():
        pytest.skip("Docker is required, but not running")

    with PostgresContainer() as pg:
        yield pg


@pytest_asyncio.fixture(scope="function")
async def test_db_url(pg_container):
    """Create a proper asyncpg URL for PostgreSQL."""
    host = pg_container.get_container_host_ip()
    port_to_expose = 5432
    if hasattr(pg_container, "port_to_expose"):
        port_to_expose = pg_container.port_to_expose
    port = pg_container.get_exposed_port(port_to_expose)

    db = "test"
    user = "test"
    password = "test"
    if hasattr(pg_container, "POSTGRES_USER"):
        user = pg_container.POSTGRES_USER
    if hasattr(pg_container, "POSTGRES_PASSWORD"):
        password = pg_container.POSTGRES_PASSWORD
    if hasattr(pg_container, "POSTGRES_DB"):
        db = pg_container.POSTGRES_DB

    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"


@pytest_asyncio.fixture(scope="function")
async def test_db_engine(test_db_url):
    """Create a SQLAlchemy engine for testing."""
    engine = create_async_engine(test_db_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def test_db(test_db_engine):
    """Create a test database session."""
    test_session = sessionmaker(test_db_engine, class_=AsyncSession, expire_on_commit=False)
    async with test_session() as session:  # type: ignore
        yield session


@pytest_asyncio.fixture(scope="function")
async def db_session(test_db):
    """Alias for test_db."""
    yield test_db


@pytest_asyncio.fixture(scope="function")
async def client(test_db):
    """Create a test client with an overridden database session."""
    app.dependency_overrides = {}

    async def override_get_db():
        yield test_db

    app.dependency_overrides[async_session] = override_get_db

    os.environ["POSTGRES_SERVER"] = "localhost"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides = {}





# =================================================================================
# OceanEmbed Fixtures
# =================================================================================

import json
import numpy as np
import xarray as xr

@pytest.fixture
def mock_scaler_json(tmp_path):
    """Provides a temporary scaler.json for the QualityGate."""
    scaler_data = {
        "means": {"temp": 15.0, "sal": 35.0},
        "stds": {"temp": 2.0, "sal": 0.5}
    }
    scaler_file = tmp_path / "scaler.json"
    scaler_file.write_text(json.dumps(scaler_data))
    return str(scaler_file)

@pytest.fixture
def dummy_ocean_dataset():
    """Provides a small dummy xarray Dataset representing inference output."""
    lon = np.linspace(-180, 180, 10)
    lat = np.linspace(-90, 90, 10)
    depth = [0, 5, 10]
    
    ds = xr.Dataset(
        coords={
            "lon": lon,
            "lat": lat,
            "depth": depth,
        }
    )
    
    shape = (len(depth), len(lat), len(lon))
    # Fill with values within bounds and perfectly scaled
    ds["temp"] = (("depth", "lat", "lon"), np.full(shape, 15.0, dtype=np.float32))
    ds["sal"] = (("depth", "lat", "lon"), np.full(shape, 35.0, dtype=np.float32))
    
    return ds
