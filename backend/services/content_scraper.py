"""
Content Scraper Service
Handles batch extraction from URLs with Jina Reader fallback and Deep Price Discovery.
"""

import asyncio
import re
import logging
from typing import List, Optional, Dict
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from models import ExtractedContent
from services.jina_reader import extract_with_jina
from agents.nodes.utils import normalize_url, get_domain_from_url
import os
import json
from config import Config
from services.extraction.orchestrator import full_site_extraction_flow
from services.crawl4ai_client import get_crawl4ai_client

logger = logging.getLogger(__name__)


# ============================================================================
# FIRECRAWL CIRCUIT BREAKER
# ============================================================================

class FirecrawlCircuitBreaker:
    """Disables Firecrawl after first 402 or 3 consecutive errors."""
    def __init__(self):
        self.disabled = False
        self.error_count = 0

    def should_skip(self) -> bool:
        return self.disabled

    def record_error(self, error_msg: str):
        self.error_count += 1
        if "402" in str(error_msg) or "Payment Required" in str(error_msg):
            self.disabled = True
            logger.error(
                "[FIRECRAWL] Circuit breaker OPEN: no credits (402). "
                "All remaining Firecrawl calls skipped."
            )
        elif self.error_count >= 3:
            self.disabled = True
            logger.error(
                "[FIRECRAWL] Circuit breaker OPEN: too many errors (%d). "
                "All remaining Firecrawl calls skipped.", self.error_count
            )

_firecrawl_breaker = FirecrawlCircuitBreaker()

async def batch_extract_with_crawl4ai(urls: List[str]) -> List[ExtractedContent]:
    """
    Novo pipeline Crawl4AI (Self-hosted) com descoberta multi-página.
    """
    if not urls:
        return []
    
    logger.info("Using Crawl4AI Multi-page Pipeline for %d URLs", len(urls))
    results = []
    
    async for client in get_crawl4ai_client():
        # Semaphore: 5 concurrent sites (4 pages each = ~20 active connections)
        sem = asyncio.Semaphore(5)
        
        async def process_site(url):
            async with sem:
                try:
                    data, extras, homepage_md = await full_site_extraction_flow(client, url)
                    
                    structured_summary = f"=== CRAWL4AI STRUCTURED EXTRACTION ===\n"
                    structured_summary += f"BRAND: {data.brand_name or 'Unknown'}\n"
                    structured_summary += f"PRICES: {json.dumps([p.model_dump() for p in data.prices])}\n"
                    structured_summary += f"STORES: {json.dumps([s.model_dump() for s in data.store_addresses])}\n"
                    if data.owner_name:
                        structured_summary += f"OWNER: {data.owner_name} ({data.owner_role or 'N/A'})\n"
                    if extras.get("contact_email"):
                        structured_summary += f"EMAIL: {extras['contact_email']}\n"
                    if extras.get("contact_linkedin"):
                        structured_summary += f"LINKEDIN: {extras['contact_linkedin']}\n"
                    
                    final_content = f"{homepage_md}\n\n{structured_summary}"
                    
                    struct_data = data.model_dump()
                    struct_data["contact_email"] = extras.get("contact_email")
                    struct_data["email_priority"] = extras.get("email_priority")
                    struct_data["email_category"] = extras.get("email_category")
                    struct_data["contact_linkedin"] = extras.get("contact_linkedin")
                    struct_data["product_images"] = data.product_images or []
                    
                    return ExtractedContent(
                        url=url,
                        content=final_content,
                        structured_data=struct_data,
                        extraction_method="crawl4ai"
                    )
                except Exception as e:
                    logger.error(f"[SCRAPER] Crawl4AI error for {url}: {e}")
                    return ExtractedContent(url=url, content="", extraction_method="failed")

        results = await asyncio.gather(*(process_site(u) for u in urls))
    return results

async def batch_extract_content(urls: List[str]) -> List[ExtractedContent]:
    """
    Batch extract content from multiple URLs.
    PRIORITY:
    1. Firecrawl Scrape (JS rendering, clean Markdown, max 15.000 chars)
    2. Jina Reader (Reliable fallback for any failures)
    """
    if not urls:
        return []

    if Config.USE_CRAWL4AI:
        return await batch_extract_with_crawl4ai(urls)

    # Legacy Firecrawl path (circuit-breaker protected)
    results = [ExtractedContent(url=url, content="") for url in urls]

    if _firecrawl_breaker.should_skip():
        logger.warning("[SCRAPER] Firecrawl circuit breaker is OPEN, skipping batch scrape")
    else:
        logger.info(f"[SCRAPER] Trying Firecrawl batch scrape for {len(urls)} URLs...")
        try:
            from firecrawl import FirecrawlApp
            app = FirecrawlApp(api_key=os.environ.get("FIRECRAWL_API_KEY"))
        except Exception as e:
            logger.error(f"[SCRAPER] Error initializing Firecrawl: {e}")
            _firecrawl_breaker.record_error(str(e))
            app = None

        BATCH_SIZE = 18
        url_batches = [
            urls[i : i + BATCH_SIZE] for i in range(0, len(urls), BATCH_SIZE)
        ]

        for batch_urls in url_batches:
            if _firecrawl_breaker.should_skip():
                break
            try:
                if not app:
                    break
                    
                extraction = app.batch_scrape(
                    batch_urls, 
                    formats=["markdown"], 
                    only_main_content=True
                )
                
                if extraction and isinstance(extraction, dict) and extraction.get("data"):
                    for result in extraction["data"]:
                        raw_content = result.get("markdown", "")
                        url = result.get("url", "")
                        if not url and result.get("metadata", {}).get("sourceURL"):
                            url = result.get("metadata")["sourceURL"]
                            
                        if raw_content and len(raw_content) > 500:
                            for idx, orig in enumerate(results):
                                if normalize_url(orig.url) == normalize_url(url) or orig.url == url:
                                    results[idx] = ExtractedContent(
                                        url=orig.url, content=raw_content[:15000]
                                    )
                                    break
            except Exception as e:
                _firecrawl_breaker.record_error(str(e))
                logger.warning(f"[SCRAPER] Firecrawl extraction error: {e}")

    # 2. Final Jina Fallback for anything still missing (Firecrawl alternative)
    final_failures = [r.url for r in results if not r.content or len(r.content) < 500]
    if final_failures:
        logger.info("Fallback to Jina Reader for %d missed URLs", len(final_failures))
        
        async def fetch_jina(url):
            try:
                # Jina is free/cheap but has some rate limits without API key.
                # However it runs JS automatically and does clean markdown.
                return await extract_with_jina(url)
            except Exception:
                return {"success": False, "url": url}
                
        # Run Jina concurrently
        jina_results = await asyncio.gather(*(fetch_jina(u) for u in final_failures))
        
        for jr in jina_results:
            if jr.get("success"):
                for idx, orig in enumerate(results):
                    if orig.url == jr["url"]:
                        results[idx] = ExtractedContent(
                            url=orig.url, content=jr.get("content", "")[:12000]
                        )
                        break

    return results


async def enrich_content_with_prices(
    contents: List[ExtractedContent],
) -> List[ExtractedContent]:
    """
    Deep Price Discovery (Smart Semantic Navigation):
    If prices aren't on homepage, it finds "Suits/Shop" links or does a targeted site search.
    """
    enriched_results = []
    urls_to_fetch_secondary = []
    indices_to_update = []

    price_pattern = r"(?:[\$€£]\s?\d{1,3}(?:[,.\s]?\d{3})*(?:[.,]\d{2})?|\d{1,3}(?:[,.\s]?\d{3})*(?:[.,]\d{2})?\s?[\$€£]|(?:price|prix|preço|preis|precio|from|starting\s+at|a\s+partir\s+de)\s*[:=]?\s*[\$€£]?\d+(?:[.,]\d{2})?)"

    for idx, item in enumerate(contents):
        if not item.content:
            enriched_results.append(item)
            continue

        if re.search(price_pattern, item.content, re.IGNORECASE):
            enriched_results.append(item)
        else:
            # Smart Navigation
            shop_link = None
            try:
                soup = BeautifulSoup(item.content, "html.parser")
                suit_keywords = [
                    "suit",
                    "fatos",
                    "fato",
                    "traje",
                    "abito",
                    "tailoring",
                    "sartorial",
                    "ceremony",
                    "wedding",
                ]
                shop_keywords = [
                    "shop",
                    "store",
                    "collection",
                    "loja",
                    "comprar",
                    "boutique",
                    "catalog",
                ]

                best_link, best_score = None, 0
                for link in soup.find_all("a", href=True):
                    href, text = (
                        link["href"].lower().strip(),
                        link.get_text(separator=" ", strip=True).lower(),
                    )
                    if (
                        not href
                        or href.startswith("#")
                        or href.startswith("javascript")
                    ):
                        continue

                    score = (
                        (10 if any(kw in text for kw in suit_keywords) else 0)
                        + (5 if any(kw in href for kw in suit_keywords) else 0)
                        + (2 if any(kw in text for kw in shop_keywords) else 0)
                        + (1 if any(kw in href for kw in shop_keywords) else 0)
                    )
                    if any(
                        kw in href
                        for kw in ["login", "account", "cart", "basket", "checkout"]
                    ):
                        score -= 50

                    if score > best_score:
                        best_score, best_link = score, link["href"]

                if best_link and best_score >= 2:
                    shop_link = urljoin(item.url, best_link)
            except Exception:
                pass

            # Fallback: Site Search with Firecrawl Extract (circuit-breaker protected)
            # Skip entirely when Crawl4AI is active — prices come from the orchestrator
            if not shop_link and not Config.USE_CRAWL4AI and not _firecrawl_breaker.should_skip():
                try:
                    from firecrawl import FirecrawlApp
                    schema = {
                        "type": "object",
                        "properties": {
                            "suit_prices": { "type": "array", "items": { "type": "number" } },
                            "average_suit_price_eur": { "type": "number" },
                            "currency_original": { "type": "string" },
                            "mtm_available": { "type": "boolean" },
                            "price_confidence": {
                                "type": "string",
                                "enum": ["high", "medium", "low", "not_found"]
                            }
                        },
                        "required": ["suit_prices", "average_suit_price_eur", "currency_original", "mtm_available", "price_confidence"]
                    }
                    
                    app = FirecrawlApp(api_key=os.environ.get("FIRECRAWL_API_KEY"))
                    extract_res = app.extract(
                        urls=[item.url],
                        prompt="Extract ONLY men's suit prices. Ignore shirts, ties, shoes, accessories. Convert to EUR if needed. Set confidence=not_found if no prices visible.",
                        schema=schema
                    )
                    
                    if extract_res and isinstance(extract_res, dict) and extract_res.get("data"):
                        extract_data = extract_res["data"][0] if isinstance(extract_res["data"], list) else extract_res["data"]
                        item.content += f"\n\n=== FIRECRAWL PRICE EXTRACT ===\n{json.dumps(extract_data, indent=2)}\n"
                        
                except Exception as e:
                    _firecrawl_breaker.record_error(str(e))
                    logger.warning(f"[SCRAPER] Firecrawl extract error on fallback: {e}")

            if shop_link and normalize_url(shop_link) != normalize_url(item.url):
                urls_to_fetch_secondary.append(shop_link)
                indices_to_update.append(idx)

            # [V2.6] Deep Dive Contact / About Us Page
            contact_link = None
            try:
                soup = BeautifulSoup(item.content, "html.parser")
                contact_keywords = [
                    "about",
                    "team",
                    "founder",
                    "contact",
                    "equipa",
                    "sobre",
                    "sobre nós",
                    "quem somos",
                    "our story",
                ]

                best_contact_link, best_contact_score = None, 0
                for link in soup.find_all("a", href=True):
                    href, text = (
                        link["href"].lower().strip(),
                        link.get_text(separator=" ", strip=True).lower(),
                    )
                    if (
                        not href
                        or href.startswith("#")
                        or href.startswith("javascript")
                        or href.startswith("mailto:")
                    ):
                        continue

                    score = (
                        10 if any(kw in text for kw in contact_keywords) else 0
                    ) + (5 if any(kw in href for kw in contact_keywords) else 0)

                    if score > best_contact_score:
                        best_contact_score, best_contact_link = score, link["href"]

                if best_contact_link and best_contact_score >= 5:
                    contact_link = urljoin(item.url, best_contact_link)
            except Exception:
                pass

            if (
                contact_link
                and normalize_url(contact_link) != normalize_url(item.url)
                and contact_link != shop_link
            ):
                urls_to_fetch_secondary.append(contact_link)
                indices_to_update.append(idx)

            enriched_results.append(item)

    if urls_to_fetch_secondary:
        secondary_contents = await batch_extract_content(urls_to_fetch_secondary)
        for i, secondary in enumerate(secondary_contents):
            if secondary.content:
                orig_idx = indices_to_update[i]
                orig_item = enriched_results[orig_idx]

                heading = "deep dive: content page"
                if (
                    "about" in secondary.url.lower()
                    or "team" in secondary.url.lower()
                    or "contact" in secondary.url.lower()
                    or "story" in secondary.url.lower()
                ):
                    heading = "deep dive: about us / contact page"
                elif (
                    "suits" in secondary.url.lower() or "shop" in secondary.url.lower()
                ):
                    heading = "deep dive: suits page"

                merged = f"{orig_item.content}\n\n{'='*40}\n=== {heading.upper()} ===\nURL: {secondary.url}\n{secondary.content}"
                enriched_results[orig_idx] = ExtractedContent(
                    url=orig_item.url, content=merged
                )

    return enriched_results
