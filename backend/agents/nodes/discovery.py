"""
Node 1: Discovery
Receives a city, generates smart search queries via LLM,
calls Exa API, and returns deduplicated raw results with content.
"""

import asyncio
import logging
import os
from typing import List, Dict, Any, Union, Tuple, Optional
from urllib.parse import urlparse

from exa_py import Exa
from models import ProspectorState
from .utils import get_llm, get_exchange_rate
from .pipeline_timing import step_begin, step_end

logger = logging.getLogger("node.discovery")

EXA_NUM_RESULTS = int(os.environ.get("EXA_NUM_RESULTS", "20"))
EXA_MAX_RETRIES = int(os.environ.get("EXA_MAX_RETRIES", "3"))
EXA_RETRY_INITIAL_SEC = float(os.environ.get("EXA_RETRY_INITIAL_SEC", "1.5"))
EXA_QUERY_MAX_CONCURRENT = max(5, min(8, int(os.environ.get("EXA_QUERY_MAX_CONCURRENT", "6"))))

EXCLUDE_DOMAINS = [
    "amazon.com", "ebay.com", "walmart.com", "target.com",
    "nordstrom.com", "saksfifthavenue.com", "neimanmarcus.com",
    "aliexpress.com", "alibaba.com",
    "yelp.com", "yellowpages.com", "tripadvisor.com",
    "trustpilot.com", "glassdoor.com", "indeed.com",
    "foursquare.com", "kompass.com",
    "facebook.com", "instagram.com", "tiktok.com",
    "twitter.com", "x.com", "linkedin.com",
    "pinterest.com", "reddit.com", "quora.com",
    "google.com", "maps.google.com",
    "wikipedia.org", "wikidata.org",
    "timeout.com", "esquire.com", "gq.com",
]


# ============================================================================
# LLM: INFER COUNTRY
# ============================================================================

async def _infer_country(city: str) -> str:
    try:
        llm = get_llm(fast=True)
        prompt = (
            f"Given the city '{city}', what country is it in? "
            "Reply with ONLY the English name of the country. No punctuation."
        )
        response = await llm.ainvoke(prompt)
        return response.content.strip()
    except Exception as e:
        logger.warning("Failed to infer country for %s: %s — defaulting to USA", city, e)
        return "USA"


# ============================================================================
# LLM: GENERATE SEARCH QUERIES
# ============================================================================

async def _generate_queries(city: str, country: str) -> List[str]:
    """
    Generate 8-12 Exa queries for independent boutiques, tailor shops, and small mid-to-high menswear.
    """
    llm = get_llm(fast=True)
    prompt = f"""You are helping Confeções Lança (Portuguese mid-to-high menswear manufacturer, suits €500-€1700) find retail partners in {city}, {country}.

Generate 8-12 web search queries to discover MEN'S SUIT / TAILORING businesses in {city}.

TARGET SEGMENT (include actively — these match real Lança clients):
- Independent menswear boutiques (1-20 stores, often single-location)
- Alfaiataria / tailor shops WITH their own retail store (bespoke or made-to-measure welcome)
- Small premium menswear brands: suits, blazers, tailored jackets as core products
- Heritage or contemporary tailoring shops, sartorial menswear

STILL EXCLUDE via query wording (do not search for):
- Fast fashion, streetwear, sportswear, sneaker brands
- Large department stores and global chains (Zara, H&M, Macy's, etc.)
- Women's-only fashion, shirt-only or accessory-only brands
- Blogs, magazines, marketplaces, directories

QUERY RULES:
- Mix English AND the local language(s) of {city}
- Use varied angles, e.g.:
  • independent menswear boutique {city}
  • alfaiataria homem {city} / men's tailoring shop {city}
  • premium suit shop {city} / negozio abiti uomo {city}
  • sartorial menswear {city} / bespoke tailor shop {city} (shop with address, not freelance)
  • men's suit maker boutique {city}

Return ONLY a JSON array of query strings. No explanation.
Example: ["query 1", "query 2", ...]"""

    try:
        response = await llm.ainvoke(prompt)
        raw = response.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        import json
        queries = json.loads(raw)
        if isinstance(queries, list) and len(queries) >= 3:
            return queries[:12]
    except Exception as e:
        logger.warning("LLM query generation failed: %s — using fallback queries", e)

    return [
        f"independent menswear boutique {city} suits",
        f"men's tailoring shop {city} {country}",
        f"premium suit shop {city}",
        f"alfaiataria homem {city}",
        f"bespoke tailor shop {city} menswear",
        f"sartorial menswear boutique {city}",
        f"men's suit maker {city} store",
        f"formal menswear retailer {city} jackets trousers",
    ]


# ============================================================================
# EXA: SEARCH WITH RETRIES
# ============================================================================

def _exa_transient(exc: BaseException) -> bool:
    s = str(exc).lower()
    needles = ("500", "502", "503", "504", "429", "internal_error",
               "try again", "timeout", "timed out", "connection reset", "temporarily")
    return any(n in s for n in needles)


async def _exa_search_with_retries(exa: Exa, query: str, exa_kwargs: Dict[str, Any]) -> Any:
    last: BaseException = RuntimeError("exa search failed")
    for attempt in range(EXA_MAX_RETRIES):
        try:
            return await asyncio.to_thread(exa.search, query, **exa_kwargs)
        except BaseException as e:
            last = e
            if attempt + 1 < EXA_MAX_RETRIES and _exa_transient(e):
                wait = EXA_RETRY_INITIAL_SEC * (2 ** attempt)
                logger.warning("Exa transient error (attempt %s/%s): %s — retry in %.1fs",
                               attempt + 1, EXA_MAX_RETRIES, e, wait)
                await asyncio.sleep(wait)
            else:
                break
    raise last


def _parse_exa_response(response: Any) -> List[Dict]:
    """Turn Exa search response into raw result dicts."""
    items: List[Dict] = []
    for result in response.results:
        url = result.url or ""
        if not url:
            continue
        text_content = result.text if hasattr(result, "text") and result.text else ""
        highlights = (
            " ".join(result.highlights)
            if hasattr(result, "highlights") and result.highlights
            else ""
        )
        items.append({
            "url": url,
            "title": result.title or "",
            "text": text_content,
            "highlights": highlights,
        })
    return items


async def _exa_search_one_query(
    exa: Exa,
    query_index: int,
    query: str,
    exa_kwargs: Dict[str, Any],
    sem: asyncio.Semaphore,
) -> Tuple[int, List[Dict], int, Optional[BaseException]]:
    """Run one discovery Exa query (retry/backoff inside). Returns (index, items, result_count, error)."""
    async with sem:
        try:
            response = await _exa_search_with_retries(exa, query, exa_kwargs)
            items = _parse_exa_response(response)
            return query_index, items, len(response.results), None
        except BaseException as e:
            return query_index, [], 0, e


def _deduplicate_by_domain(results: List[Dict]) -> List[Dict]:
    seen = set()
    unique = []
    for item in results:
        url = item.get("url", "")
        domain = urlparse(url).netloc.lower().replace("www.", "")
        if domain and domain not in seen:
            seen.add(domain)
            unique.append(item)
    return unique


# ============================================================================
# MAIN NODE
# ============================================================================

async def discovery_node(state: Union[ProspectorState, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Node 1: Discovery.
    Receives city → infers country → generates queries → calls Exa → deduplicates.
    Returns raw search results with full Exa content for downstream processing.
    """
    target_city = state.target_city if hasattr(state, "target_city") else state.get("target_city", "")

    t_node = step_begin(logger, "N1_DISCOVERY", target_city,
                        "Inferir país, gerar queries via LLM, pesquisar no Exa e deduplicar.")

    progress = [f"🚀 A iniciar pesquisa em {target_city}…"]

    # 1. Infer country
    target_country = await _infer_country(target_city)
    logger.info("País inferido: %s → %s", target_city, target_country)
    progress.append(f"🌍 País identificado: {target_country}")

    # 2. Exchange rate (for downstream price conversion)
    exchange_rate = await get_exchange_rate()

    # 3. Generate queries via LLM
    t_queries = step_begin(logger, "N1a_QUERIES", target_city,
                           "Gerar queries de pesquisa com LLM.")
    queries = await _generate_queries(target_city, target_country)
    step_end(logger, "N1a_QUERIES", target_city, t_queries, queries=len(queries))

    for i, q in enumerate(queries):
        logger.info("  Query %d: %s", i + 1, q)

    progress.append(f"🔎 {len(queries)} pesquisas preparadas — a procurar marcas de moda masculina…")

    # 4. Call Exa for all queries in parallel (capped concurrency)
    exa = Exa(api_key=os.environ.get("EXA_API_KEY"))
    all_raw: List[Dict] = []
    exa_kwargs = {
        "num_results": EXA_NUM_RESULTS,
        "type": "auto",
        "exclude_domains": EXCLUDE_DOMAINS,
        "contents": {"text": {"maxCharacters": 10000}, "highlights": True},
    }

    t_exa = step_begin(
        logger, "N1b_EXA_SEARCH", target_city,
        f"Executar {len(queries)} queries no Exa (max {EXA_QUERY_MAX_CONCURRENT} paralelas).",
    )
    sem = asyncio.Semaphore(EXA_QUERY_MAX_CONCURRENT)
    query_outcomes = await asyncio.gather(
        *[
            _exa_search_one_query(exa, i, query, exa_kwargs, sem)
            for i, query in enumerate(queries)
        ]
    )
    query_outcomes.sort(key=lambda x: x[0])

    for query_index, items, result_count, err in query_outcomes:
        qn = query_index + 1
        if err is not None:
            logger.error("  Exa Q%d failed: %s", qn, err)
        else:
            all_raw.extend(items)
            logger.info("  Exa Q%d: %d results", qn, result_count)

    step_end(logger, "N1b_EXA_SEARCH", target_city, t_exa,
             raw_results=len(all_raw), parallel_cap=EXA_QUERY_MAX_CONCURRENT)

    # 5. Deduplicate by domain
    unique_results = _deduplicate_by_domain(all_raw)
    logger.info("Dedup: %d raw → %d unique domains", len(all_raw), len(unique_results))
    progress.append(f"🏬 {len(unique_results)} marcas encontradas para analisar")

    step_end(logger, "N1_DISCOVERY", target_city, t_node,
             queries=len(queries), unique_domains=len(unique_results))

    return {
        "target_country": target_country,
        "exchange_rate": exchange_rate,
        "search_results_raw": unique_results,
        "progress": progress,
    }
