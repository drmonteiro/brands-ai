"""First-load protections: connection retry, cities cache, request timing."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest
from fastapi.testclient import TestClient

from services import database as db
from services import postgres
from services.postgres import retry_on_connection_error


@pytest.mark.parametrize("error", [
    ConnectionResetError("dropped"),
    asyncio.TimeoutError(),
    asyncpg.InterfaceError("connection is closed"),
    asyncpg.ConnectionDoesNotExistError("gone"),
])
async def test_retries_once_on_connection_errors(error, monkeypatch):
    monkeypatch.setattr(postgres, "CONNECTION_RETRY_DELAY_SEC", 0)
    calls = {"n": 0}

    @retry_on_connection_error
    async def query():
        calls["n"] += 1
        if calls["n"] == 1:
            raise error
        return "ok"

    assert await query() == "ok"
    assert calls["n"] == 2


async def test_gives_up_after_one_retry(monkeypatch):
    monkeypatch.setattr(postgres, "CONNECTION_RETRY_DELAY_SEC", 0)
    fn = AsyncMock(side_effect=ConnectionResetError("dropped"))
    with pytest.raises(ConnectionResetError):
        await retry_on_connection_error(fn)()
    assert fn.await_count == 2


async def test_does_not_retry_query_errors():
    fn = AsyncMock(side_effect=ValueError("bad"))
    with pytest.raises(ValueError):
        await retry_on_connection_error(fn)()
    assert fn.await_count == 1


def _pool_returning(rows, tag="UPDATE 1"):
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=rows)
    conn.execute = AsyncMock(return_value=tag)
    acquire = MagicMock()
    acquire.__aenter__ = AsyncMock(return_value=conn)
    acquire.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.acquire.return_value = acquire
    return pool, conn


@pytest.fixture(autouse=True)
def _empty_cache():
    db.clear_cities_cache()
    yield
    db.clear_cities_cache()


async def test_cities_are_cached_between_calls(monkeypatch):
    pool, conn = _pool_returning([{"city": "london", "total_prospects": 3}])
    monkeypatch.setattr(db.PostgresManager, "get_pool", AsyncMock(return_value=pool))
    first = await db.get_all_searched_cities()
    second = await db.get_all_searched_cities()
    assert first == second
    assert conn.fetch.await_count == 1


async def test_changes_clear_the_cities_cache(monkeypatch):
    pool, conn = _pool_returning([{"city": "london", "total_prospects": 3}])
    monkeypatch.setattr(db.PostgresManager, "get_pool", AsyncMock(return_value=pool))
    await db.get_all_searched_cities()
    await db.update_prospect_status("id", "contacted")
    await db.get_all_searched_cities()
    await db.delete_prospect("id")
    await db.get_all_searched_cities()
    assert conn.fetch.await_count == 3


async def test_cached_cities_cannot_be_changed_by_callers(monkeypatch):
    pool, _ = _pool_returning([{"city": "london", "total_prospects": 3}])
    monkeypatch.setattr(db.PostgresManager, "get_pool", AsyncMock(return_value=pool))
    (await db.get_all_searched_cities())[0]["city"] = "changed"
    assert (await db.get_all_searched_cities())[0]["city"] == "london"


def test_requests_report_their_duration(caplog):
    from main import app

    with caplog.at_level("INFO", logger="api.requests"):
        res = TestClient(app).get("/health")
    assert res.headers["server-timing"].startswith("app;dur=")
    assert "/health" in caplog.text
    assert "uptime_s=" in caplog.text
