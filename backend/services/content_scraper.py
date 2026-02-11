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
from services.firecrawl_service import firecrawl_service
from agents.nodes.utils import get_tavily_client, normalize_url, get_domain_from_url

async def batch_extract_content(urls: List[str]) -> List[ExtractedContent]:
    """
    Batch extract content from multiple URLs.
    PRIORITY:
    1. Firecrawl (High quality Markdown, JS rendering)
    2. Tavily Extract (Fast, good coverage)
    3. Jina Reader (Reliable fallback for specific URLs)
    """
    if not urls:
        return []

    # 1. Try Firecrawl first for ALL urls
    print(f"[SCRAPER] Trying Firecrawl for {len(urls)} URLs...")
    results = await firecrawl_service.batch_extract(urls)
    
    # Check what failed (None or very short content)
    failed_urls = [r.url for r in results if not r.content or len(r.content) < 500]
    
    if not failed_urls:
        return results

    # 2. Try Tavily Extract for failures
    print(f"[SCRAPER] Firecrawl missed/short on {len(failed_urls)} URLs. Trying Tavily Extract fallback...")
    client = get_tavily_client()
    BATCH_SIZE = 18
    url_batches = [failed_urls[i:i + BATCH_SIZE] for i in range(0, len(failed_urls), BATCH_SIZE)]
    
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
                            if orig.url == url:
                                results[idx] = ExtractedContent(url=url, content=raw_content[:12000])
                                break
        except Exception as e:
            print(f"[SCRAPER] Tavily fallback error: {e}")

    # 3. Final Jina Fallback for anything still missing
    final_failures = [r.url for r in results if not r.content or len(r.content) < 500]
    if final_failures:
        print(f"[SCRAPER] Final fallback to Jina for {len(final_failures)} URLs...")
        for url in final_failures:
            try:
                jina_result = await extract_with_jina(url)
                if jina_result["success"]:
                    for idx, orig in enumerate(results):
                        if orig.url == url:
                            results[idx] = ExtractedContent(url=url, content=jina_result["content"][:12000])
                            break
            except Exception:
                pass

    return results

async def enrich_content_with_prices(contents: List[ExtractedContent]) -> List[ExtractedContent]:
    """
    Deep Price Discovery (Smart Semantic Navigation):
    If prices aren't on homepage, it finds "Suits/Shop" links or does a targeted site search.
    """
    enriched_results = []
    urls_to_fetch_secondary = []
    indices_to_update = []
    
    price_pattern = r'(?:[\$€£]\s?\d{1,3}(?:[,.\s]?\d{3})*(?:[.,]\d{2})?|\d{1,3}(?:[,.\s]?\d{3})*(?:[.,]\d{2})?\s?[\$€£]|(?:price|prix|preço|preis|precio|from|starting\s+at|a\s+partir\s+de)\s*[:=]?\s*[\$€£]?\d+(?:[.,]\d{2})?)'
    
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
                soup = BeautifulSoup(item.content, 'html.parser')
                suit_keywords = ['suit', 'fatos', 'fato', 'traje', 'abito', 'tailoring', 'sartorial', 'ceremony', 'wedding']
                shop_keywords = ['shop', 'store', 'collection', 'loja', 'comprar', 'boutique', 'catalog']
                
                best_link, best_score = None, 0
                for link in soup.find_all('a', href=True):
                    href, text = link['href'].lower().strip(), link.get_text(separator=' ', strip=True).lower()
                    if not href or href.startswith('#') or href.startswith('javascript'): continue
                    
                    score = (10 if any(kw in text for kw in suit_keywords) else 0) + \
                            (5 if any(kw in href for kw in suit_keywords) else 0) + \
                            (2 if any(kw in text for kw in shop_keywords) else 0) + \
                            (1 if any(kw in href for kw in shop_keywords) else 0)
                    if any(kw in href for kw in ['login', 'account', 'cart', 'basket', 'checkout']): score -= 50
                    
                    if score > best_score:
                        best_score, best_link = score, link['href']
                
                if best_link and best_score >= 2:
                    shop_link = urljoin(item.url, best_link)
            except Exception:
                pass
            
            # Fallback: Site Search
            if not shop_link:
                try:
                    domain = get_domain_from_url(item.url)
                    found = get_tavily_client().search(query=f'site:{domain} "suits" price', search_depth="basic", max_results=1)
                    if found.get("results"):
                        found_url = found["results"][0]["url"]
                        if normalize_url(found_url) != normalize_url(item.url):
                            shop_link = found_url
                except Exception:
                    pass

            if shop_link and normalize_url(shop_link) != normalize_url(item.url):
                urls_to_fetch_secondary.append(shop_link)
                indices_to_update.append(idx)
            
            enriched_results.append(item)

    if urls_to_fetch_secondary:
        secondary_contents = await batch_extract_content(urls_to_fetch_secondary)
        for i, secondary in enumerate(secondary_contents):
            if secondary.content:
                orig_idx = indices_to_update[i]
                orig_item = enriched_results[orig_idx]
                merged = f"{orig_item.content}\n\n{'='*40}\n=== DEEP DIVE: SUITS PAGE ===\nURL: {secondary.url}\n{secondary.content}"
                enriched_results[orig_idx] = ExtractedContent(url=orig_item.url, content=merged)

    return enriched_results
