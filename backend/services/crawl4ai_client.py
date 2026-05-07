import asyncio
import httpx
import logging
import json
from typing import List, Dict, Any, Optional, AsyncGenerator
from pydantic import BaseModel, Field
from config import Config

logger = logging.getLogger(__name__)

class Crawl4AIResponse(BaseModel):
    success: bool
    url: str
    status_code: Optional[int] = None
    raw_markdown: Optional[str] = None
    fit_markdown: Optional[str] = None
    cleaned_html: Optional[str] = None
    internal_links: List[str] = Field(default_factory=list)
    error_message: Optional[str] = None

    @property
    def best_markdown(self) -> str:
        """Returns fit_markdown if it exists and is substantial, else raw."""
        if self.fit_markdown and len(self.fit_markdown) > 200:
            return self.fit_markdown
        return self.raw_markdown or ""



class Crawl4AIClient:
    def __init__(self):
        self.base_url = Config.CRAWL4AI_BASE_URL.rstrip('/')
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=50)
        )

    async def close(self):
        await self._client.aclose()

    async def _request_with_retry(self, method: str, endpoint: str, json_data: Dict = None, timeout_seconds: float = 30.0) -> Dict:
        max_retries = 3
        base_delay = 1.0

        for attempt in range(max_retries):
            try:
                response = await self._client.request(
                    method, endpoint, json=json_data, timeout=httpx.Timeout(timeout_seconds)
                )
                response.raise_for_status()
                return response.json()
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout, httpx.NetworkError) as e:
                if attempt == max_retries - 1:
                    logger.error(f"[CRAWL4AI] Network error after {max_retries} attempts: {e}")
                    raise
                delay = base_delay * (2 ** attempt)
                logger.warning(f"[CRAWL4AI] Network issue ({type(e).__name__}), retrying in {delay}s...")
                await asyncio.sleep(delay)
            except httpx.HTTPStatusError as e:
                # Retry for 5xx Server Errors only
                if e.response.status_code >= 500 and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"[CRAWL4AI] Server error {e.response.status_code}, retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    raise
        
        raise RuntimeError("Unreachable: retry loop exhausted without return or raise")

    async def health_check(self) -> bool:
        try:
            res = await self._request_with_retry("GET", "/health", timeout_seconds=10.0)
            return res.get("status") in ["ok", "healthy"]
        except Exception as e:
            logger.error(f"[CRAWL4AI] Health check failed: {e}")
            return False

    def _parse_response(self, result: Dict, url: str) -> Crawl4AIResponse:
        data = result.get("results", [result])[0] if "results" in result else result
        
        if data.get("error"):
            logger.error(f"[CRAWL4AI] Scrape returned error for {url}: {data['error']}")
            return Crawl4AIResponse(success=False, url=url, error_message=data["error"], status_code=200)

        # Parse markdown variants
        md_field = data.get("markdown") or data.get("content")
        raw_md = None
        fit_md = None
        
        if isinstance(md_field, dict):
            raw_md = md_field.get("raw_markdown")
            fit_md = md_field.get("fit_markdown")
        else:
            raw_md = md_field

        # Parse links
        internal_links = []
        links_data = data.get("links", {})
        if isinstance(links_data, dict) and "internal" in links_data:
            internal_links = [l.get("href") for l in links_data["internal"] if l.get("href")]

        return Crawl4AIResponse(
            success=True,
            url=url,
            raw_markdown=raw_md,
            fit_markdown=fit_md,
            cleaned_html=data.get("cleaned_html"),
            internal_links=internal_links,
            status_code=200
        )

    def _get_base_crawler_config(self) -> Dict:
        return {
            "magic": True,
            "wait_until": "load",
            "cache_mode": "BYPASS"
        }

    async def scrape(self, url: str) -> Crawl4AIResponse:
        timeout = 90.0
        payload = {
            "urls": [url],
            "browser_config": {
                "headless": True, 
                "enable_stealth": True,
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            },
            "crawler_config": self._get_base_crawler_config()
        }
        logger.info(f"[CRAWL4AI] Scraping {url}")
        try:
            result = await self._request_with_retry("POST", "/crawl", json_data=payload, timeout_seconds=timeout)
            return self._parse_response(result, url)
        except httpx.HTTPError as e:
            logger.error(f"[CRAWL4AI] Scrape HTTP error for {url}: {e}")
            status_code = e.response.status_code if isinstance(e, httpx.HTTPStatusError) else None
            return Crawl4AIResponse(success=False, url=url, error_message=str(e), status_code=status_code)



    async def crawl_deep(self, url: str, max_depth: int = 3, max_pages: int = 20) -> List[Crawl4AIResponse]:
        timeout = 120.0
        # Wait for instructions on REST payload structure for deep crawl scorers in Crawl4AI
        raise NotImplementedError("Deep crawl to be implemented once REST structure is validated.")

    async def prefetch_map(self, url: str) -> List[str]:
        """
        Scrapes the homepage to get all internal links.
        """
        res = await self.scrape(url)
        if res.success:
            return res.internal_links
        return []

async def get_crawl4ai_client() -> AsyncGenerator[Crawl4AIClient, None]:
    client = Crawl4AIClient()
    try:
        yield client
    finally:
        await client.close()
