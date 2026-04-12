import asyncio
from services.database import get_db_conn

async def check_washington():
    conn = await get_db_conn()
    if not conn:
        print("Could not connect to DB")
        return
        
    try:
        # Check prospects with city = 'Washington' (or similar)
        prospects = await conn.fetch("SELECT name, city, fit_score, price_source, is_appointment_only FROM prospects WHERE city ILIKE 'Washington%'")
        print(f"\n--- FINAL DB PROSPECTS SAVED FOR WASHINGTON: {len(prospects)} ---")
        for p in prospects:
            app_only = " [Appt Only]" if p['is_appointment_only'] else ""
            print(f" - {p['name']} (Score: {p['fit_score']}) | {p['price_source']}{app_only}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(check_washington())
