import asyncio
import os
import sys
from dotenv import load_dotenv

# Ensure we can import from backend
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))
load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'backend', '.env'))

from services.crawl4ai_client import get_crawl4ai_client

async def test_isaia():
    async for client in get_crawl4ai_client():
        url = "https://www.isaia.it"
        print(f"Scraping {url}...")
        response = await client.scrape(url)
        print(f"Success: {response.success}")
        if response.success:
            print(f"fit_markdown length: {len(response.fit_markdown or '')}")
            print(f"raw_markdown length: {len(response.raw_markdown or '')}")
            print(f"cleaned_html length: {len(response.cleaned_html or '')}")
            if response.fit_markdown:
                print(f"Snippet: {response.fit_markdown[:200]}...")
        else:
            print(f"Error: {response.error_message}")

if __name__ == "__main__":
    asyncio.run(test_isaia())
