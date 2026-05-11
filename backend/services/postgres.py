import os
import asyncpg
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

import ssl

class PostgresManager:
    _pool: Optional[asyncpg.Pool] = None

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

            try:
                if dsn:
                    cls._pool = await asyncpg.create_pool(
                        dsn=dsn,
                        min_size=1,
                        max_size=5,
                        max_inactive_connection_lifetime=300,
                        ssl=ctx,
                        command_timeout=60,
                        server_settings=cls._server_settings,
                    )
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
                    
                    cls._pool = await asyncpg.create_pool(
                        user=user,
                        password=password,
                        database=database,
                        host=host,
                        port=port,
                        min_size=1,
                        max_size=5,
                        max_inactive_connection_lifetime=300,
                        ssl=ctx,
                        command_timeout=60,
                        server_settings=cls._server_settings,
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
