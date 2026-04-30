"""
Content Scraper Service
Handles batch extraction from URLs with Jina Reader fallback and Deep Price Discovery.
"""

import asyncio
import re
from typing import List, Optional, Dict
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from models import ExtractedContent
from services.jina_reader import extract_with_jina
from agents.nodes.utils import get_tavily_client, normalize_url, get_domain_from_url
import os
from firecrawl import FirecrawlApp
import json


async def batch_extract_content(urls: List[str]) -> List[ExtractedContent]:
    """
    Batch extract content from multiple URLs.
    PRIORITY:
    1. Firecrawl Scrape (JS rendering, clean Markdown, max 15.000 chars)
    2. Jina Reader (Reliable fallback for any failures)
    """
    if not urls:
        return []

    # Initialize results with empty content
    results = [ExtractedContent(url=url, content="") for url in urls]

    # 1. Try Firecrawl Scrape for ALL urls
    print(f"[SCRAPER] Trying Firecrawl batch scrape for {len(urls)} URLs...")
    
    try:
        app = FirecrawlApp(api_key=os.environ.get("FIRECRAWL_API_KEY"))
    except Exception as e:
        print(f"[SCRAPER] Error initializing Firecrawl: {e}")
        app = None

    BATCH_SIZE = 18
    url_batches = [
        urls[i : i + BATCH_SIZE] for i in range(0, len(urls), BATCH_SIZE)
    ]

    for batch_urls in url_batches:
        try:
            if not app:
                break
                
            extraction = app.batch_scrape(
                batch_urls, 
                formats=["markdown"], 
                only_main_content=True
            )
            
            # Firecrawl returns a dict with 'data' array where each item has 'url' and 'markdown'
            if extraction and isinstance(extraction, dict) and extraction.get("data"):
                for result in extraction["data"]:
                    raw_content = result.get("markdown", "")
                    url = result.get("url", "")
                    # Also fallback to sourceURL if url is empty
                    if not url and result.get("metadata", {}).get("sourceURL"):
                        url = result.get("metadata")["sourceURL"]
                        
                    if raw_content and len(raw_content) > 500:
                        # Find the index in original results to overwrite
                        for idx, orig in enumerate(results):
                            if normalize_url(orig.url) == normalize_url(url) or orig.url == url:
                                results[idx] = ExtractedContent(
                                    url=orig.url, content=raw_content[:15000] # Limite máximo: 15.000 chars
                                )
                                break
        except Exception as e:
            print(f"[SCRAPER] Firecrawl extraction error: {e}")

    # 2. Final Jina Fallback for anything still missing (Firecrawl alternative)
    final_failures = [r.url for r in results if not r.content or len(r.content) < 500]
    if final_failures:
        print(f"[SCRAPER] Fallback to Jina Reader for {len(final_failures)} missed URLs...")
        
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

            # Fallback: Site Search with Firecrawl Extract
            if not shop_link:
                try:
                    domain = get_domain_from_url(item.url)
                    
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
                    
                    # Store extraction directly in the content string so downstream regex extractor
                    # and GPT stages can utilize the price_confidence and the structured output
                    if extract_res and isinstance(extract_res, dict) and extract_res.get("data"):
                        extract_data = extract_res["data"][0] if isinstance(extract_res["data"], list) else extract_res["data"]
                        item.content += f"\n\n=== FIRECRAWL PRICE EXTRACT ===\n{json.dumps(extract_data, indent=2)}\n"
                        
                except Exception as e:
                    print(f"[SCRAPER] Firecrawl extract error on fallback: {e}")

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
