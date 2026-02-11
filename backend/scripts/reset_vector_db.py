import asyncio
import os
import sys

# Add current directory to path
sys.path.append(os.getcwd())

from services.postgres import PostgresManager
from services.database import init_database

async def reset_lanca_clients():
    print("Connecting to database...")
    pool = await PostgresManager.get_pool()
    async with pool.acquire() as conn:
        print("Dropping table lanca_clients...")
        await conn.execute("DROP TABLE IF EXISTS lanca_clients CASCADE")
        print("Table dropped.")
    
    print("Re-initializing database schema...")
    await init_database()
    print("Done.")
    await PostgresManager.close()

if __name__ == "__main__":
    asyncio.run(reset_lanca_clients())
