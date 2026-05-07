import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from services.crawl4ai_client import get_crawl4ai_client

async def test_scrape():
    print("Testing Crawl4AI Health Check...")
    async for client in get_crawl4ai_client():
        is_healthy = await client.health_check()
        print(f"Health check status: {'Healthy ✅' if is_healthy else 'Unhealthy ❌'}")
        
        if is_healthy:
            print("\nTesting Scrape on https://example.com ...")
            response = await client.scrape("https://example.com")
            print(f"Success: {response.success}")
            print(f"Status Code: {response.status_code}")
            if response.success:
                print(f"Markdown snippet: {response.markdown[:200]}...")
            else:
                print(f"Error: {response.error_message}")

if __name__ == "__main__":
    asyncio.run(test_scrape())
