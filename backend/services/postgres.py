import asyncio
import functools
import logging
import os
import asyncpg
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

import ssl

logger = logging.getLogger("services.postgres")

# Errors that mean the connection failed, not the query, so trying again is safe.
_CONNECTION_ERRORS = (
    asyncpg.PostgresConnectionError,
    asyncpg.InterfaceError,
    OSError,  # includes ConnectionError and TimeoutError
)
CONNECTION_RETRY_DELAY_SEC = 0.3


def retry_on_connection_error(fn):
    """Retry a read once if the connection fails, as a dropped idle connection would."""

    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except _CONNECTION_ERRORS as e:
            logger.warning("DB_CONNECTION_RETRY %s: %r", fn.__name__, e)
            await asyncio.sleep(CONNECTION_RETRY_DELAY_SEC)
            return await fn(*args, **kwargs)

    return wrapper


class PostgresManager:
    _pool: Optional[asyncpg.Pool] = None
    _POOL_CONNECT_TIMEOUT_SEC = 20
    # asyncpg waits 60s by default to open a connection and to run a query, long
    # enough to look like a frozen page. Fail fast and let the retry handle it.
    _CONNECT_TIMEOUT_SEC = 10
    _COMMAND_TIMEOUT_SEC = 20
    # Replace idle connections before the database or network drops them.
    _MAX_IDLE_SEC = 60

    # TCP keepalive settings to prevent Neon/Azure from dropping idle connections
    _server_settings = {
        "tcp_keepalives_idle": "30",
        "tcp_keepalives_interval": "10",
        "tcp_keepalives_count": "5",
    }

    @classmethod
    async def get_pool(cls) -> asyncpg.Pool:
        if cls._pool is None:
            dsn = os.getenv("SYNC_DATABASE_URL") or os.getenv("DATABASE_URL")
            
            if dsn and not dsn.strip():
                dsn = None
            
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            async def _create_pool(**kwargs):
                return await asyncio.wait_for(
                    asyncpg.create_pool(
                        min_size=1,
                        max_size=5,
                        max_inactive_connection_lifetime=cls._MAX_IDLE_SEC,
                        ssl=ctx,
                        timeout=cls._CONNECT_TIMEOUT_SEC,
                        command_timeout=cls._COMMAND_TIMEOUT_SEC,
                        server_settings=cls._server_settings,
                        **kwargs,
                    ),
                    timeout=cls._POOL_CONNECT_TIMEOUT_SEC,
                )

            try:
                if dsn:
                    cls._pool = await _create_pool(dsn=dsn)
                else:
                    user = os.getenv("POSTGRES_USER")
                    if not user or not user.strip(): user = "lanca"
                        
                    password = os.getenv("POSTGRES_PASSWORD")
                    if not password or not password.strip(): password = "lanca_password"
                        
                    database = os.getenv("POSTGRES_DB")
                    if not database or not database.strip(): database = "lanca_leads"
                        
                    host = os.getenv("POSTGRES_HOST")
                    if not host or not host.strip(): host = "localhost"
                        
                    port_str = os.getenv("POSTGRES_PORT")
                    if not port_str or not port_str.strip(): port_str = "5432"
                    port = int(port_str)
                    
                    cls._pool = await _create_pool(
                        user=user,
                        password=password,
                        database=database,
                        host=host,
                        port=port,
                    )
            except Exception as e:
                print(f"[DATABASE] Error creating connection pool: {e}")
                raise
        return cls._pool

    @classmethod
    async def close(cls):
        if cls._pool:
            await cls._pool.close()
            cls._pool = None

async def get_db():
    pool = await PostgresManager.get_pool()
    async with pool.acquire() as connection:
        yield connection

async def execute_query(query: str, *args):
    pool = await PostgresManager.get_pool()
    async with pool.acquire() as connection:
        return await connection.execute(query, *args)

async def fetch_rows(query: str, *args):
    pool = await PostgresManager.get_pool()
    async with pool.acquire() as connection:
        return await connection.fetch(query, *args)

async def fetch_one(query: str, *args):
    pool = await PostgresManager.get_pool()
    async with pool.acquire() as connection:
        return await connection.fetchrow(query, *args)
