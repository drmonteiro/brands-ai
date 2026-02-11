"""
Firecrawl Service
High-quality web scraping with Markdown conversion and rate limiting.
"""
import asyncio
from typing import List, Optional, Dict
from firecrawl import FirecrawlApp
from config import Config
from models import ExtractedContent

class FirecrawlService:
    _instance = None
    _semaphore = asyncio.Semaphore(5) # Limit concurrency to 5 sites at a time

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FirecrawlService, cls).__new__(cls)
            cls._instance.app = FirecrawlApp(api_key=Config.FIRECRAWL_API_KEY)
        return cls._instance

    async def extract_content(self, url: str) -> Optional[str]:
        """
        Extract content from a single URL using Firecrawl.
        Converts to clean Markdown.
        """
        if not Config.FIRECRAWL_API_KEY:
            print("[FIRECRAWL] ⚠️ API Key missing, skipping...")
            return None

        async with self._semaphore:
            try:
                print(f"[FIRECRAWL] Extracting: {url}")
                # firecrawl-py 1.x uses scrape_url (sync but we can run in thread)
                # Note: Newer SDKs might have async support, check docs if needed
                # For now using it safely.
                
                # Perform the scrape using the specific keyword arguments required by firecrawl-py v2
                scrape_result = await asyncio.to_thread(
                    self.app.scrape, 
                    url=url, 
                    formats=['markdown']
                )
                
                if not scrape_result:
                    return None

                # Handle Document object from v2 SDK
                if hasattr(scrape_result, 'markdown') and scrape_result.markdown:
                    return scrape_result.markdown
                if hasattr(scrape_result, 'content') and getattr(scrape_result, 'content'):
                    return getattr(scrape_result, 'content')

                # Fallback for dict-style response (v1 or different SDK versions)
                if isinstance(scrape_result, dict):
                    data = scrape_result.get('data', scrape_result)
                    if isinstance(data, dict):
                        return data.get('markdown') or data.get('content') or scrape_result.get('markdown')
                
                return None
            except Exception as e:
                print(f"[FIRECRAWL] ❌ Error scraping {url}: {e}")
                return None

    async def batch_extract(self, urls: List[str]) -> List[ExtractedContent]:
        """
        Extract content from multiple URLs concurrently with rate limiting.
        """
        tasks = [self.extract_content(url) for url in urls]
        contents = await asyncio.gather(*tasks)
        
        results = []
        for url, content in zip(urls, contents):
            results.append(ExtractedContent(url=url, content=content))
        
        return results

# Singleton instance
firecrawl_service = FirecrawlService()
