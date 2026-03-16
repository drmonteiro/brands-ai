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


async def batch_extract_content(urls: List[str]) -> List[ExtractedContent]:
    """
    Batch extract content from multiple URLs.
    PRIORITY:
    1. Tavily Extract (Fast, cost-effective, handles batches)
    2. Jina Reader (Reliable fallback for JS-heavy sites)
    """
    if not urls:
        return []

    # Initialize results with empty content
    results = [ExtractedContent(url=url, content="") for url in urls]

    # 1. Try Tavily Extract for ALL urls
    print(f"[SCRAPER] Trying Tavily Extract for {len(urls)} URLs...")
    client = get_tavily_client()
    BATCH_SIZE = 18
    url_batches = [
        urls[i : i + BATCH_SIZE] for i in range(0, len(urls), BATCH_SIZE)
    ]

    for batch_urls in url_batches:
        try:
            extraction = client.extract(urls=batch_urls)
            if extraction.get("results"):
                for result in extraction["results"]:
                    raw_content = result.get("raw_content", "")
                    url = result.get("url", "")
                    if raw_content and len(raw_content) > 500:
                        # Find the index in original results to overwrite
                        for idx, orig in enumerate(results):
                            if normalize_url(orig.url) == normalize_url(url) or orig.url == url:
                                results[idx] = ExtractedContent(
                                    url=orig.url, content=raw_content[:12000]
                                )
                                break
        except Exception as e:
            print(f"[SCRAPER] Tavily extraction error: {e}")

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

            # Fallback: Site Search
            if not shop_link:
                try:
                    domain = get_domain_from_url(item.url)
                    found = get_tavily_client().search(
                        query=f'site:{domain} "suits" price',
                        search_depth="basic",
                        max_results=1,
                    )
                    if found.get("results"):
                        found_url = found["results"][0]["url"]
                        if normalize_url(found_url) != normalize_url(item.url):
                            shop_link = found_url
                except Exception:
                    pass

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
