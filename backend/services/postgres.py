import os
import asyncpg
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

import ssl

class PostgresManager:
    _pool: Optional[asyncpg.Pool] = None

    @classmethod
    async def get_pool(cls) -> asyncpg.Pool:
        if cls._pool is None:
            dsn = os.getenv("SYNC_DATABASE_URL") or os.getenv("DATABASE_URL")
            
            # Treat empty strings as None
            if dsn and not dsn.strip():
                dsn = None
            
            # Azure/Neon usually require explicit SSL context for asyncpg
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            try:
                if dsn:
                    cls._pool = await asyncpg.create_pool(
                        dsn=dsn,
                        min_size=1,
                        max_size=10,
                        ssl=ctx,
                        command_timeout=60
                    )
                else:
                    # Robust fallbacks for empty environment variables in Azure
                    user = os.getenv("POSTGRES_USER")
                    if not user or not user.strip(): user = "neondb_owner"
                        
                    password = os.getenv("POSTGRES_PASSWORD")
                    if not password or not password.strip(): password = "npg_SXtODez2Lg5j"
                        
                    database = os.getenv("POSTGRES_DB")
                    if not database or not database.strip(): database = "neondb"
                        
                    host = os.getenv("POSTGRES_HOST")
                    if not host or not host.strip(): host = "ep-young-shape-a9xs7bk9-pooler.gwc.azure.neon.tech"
                        
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
                        max_size=10,
                        ssl=ctx,
                        command_timeout=60
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
