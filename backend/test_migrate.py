import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

async def add_column():
    dsn = os.getenv("SYNC_DATABASE_URL")
    pool = await asyncpg.create_pool(dsn=dsn)
    try:
        async with pool.acquire() as conn:
            await conn.execute('ALTER TABLE prospects ADD COLUMN IF NOT EXISTS price_note VARCHAR(255)')
            print("Successfully added price_note to database!")
    finally:
        await pool.close()

asyncio.run(add_column())
