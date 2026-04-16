import asyncio
import os
from dotenv import load_dotenv
import asyncpg

load_dotenv()

async def check_toronto():
    dsn = os.getenv("SYNC_DATABASE_URL")
    pool = await asyncpg.create_pool(dsn=dsn)
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT name, city, avg_suit_price_eur FROM prospects ORDER BY discovered_at DESC LIMIT 10")
            print(f"Found {len(rows)} recent brands")
            for r in rows:
                print(dict(r))
    finally:
        await pool.close()
            
asyncio.run(check_toronto())
