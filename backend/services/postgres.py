import os
import asyncpg
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

class PostgresManager:
    _pool: Optional[asyncpg.Pool] = None

    @classmethod
    async def get_pool(cls) -> asyncpg.Pool:
        if cls._pool is None:
            user = os.getenv("POSTGRES_USER", "lanca")
            password = os.getenv("POSTGRES_PASSWORD", "lanca_password")
            database = os.getenv("POSTGRES_DB", "lanca_leads")
            host = os.getenv("POSTGRES_HOST", "localhost")
            port = os.getenv("POSTGRES_PORT", "5432")
            
            cls._pool = await asyncpg.create_pool(
                user=user,
                password=password,
                database=database,
                host=host,
                port=int(port),
                min_size=5,
                max_size=20
            )
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
