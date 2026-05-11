"""
Node 1: Discovery
Receives a city, generates smart search queries via LLM,
calls Exa API, and returns deduplicated raw results with content.
"""

import asyncio
import logging
import os
from typing import List, Dict, Any, Union, Tuple
from urllib.parse import urlparse

from exa_py import Exa
from models import ProspectorState
from .utils import get_llm, get_exchange_rate
from .pipeline_timing import step_begin, step_end

logger = logging.getLogger("node.discovery")

EXA_NUM_RESULTS = int(os.environ.get("EXA_NUM_RESULTS", "20"))
EXA_MAX_RETRIES = int(os.environ.get("EXA_MAX_RETRIES", "3"))
EXA_RETRY_INITIAL_SEC = float(os.environ.get("EXA_RETRY_INITIAL_SEC", "1.5"))

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
    Use LLM to generate 8-10 Exa search queries tailored to the city.
    Focus: men's suit BRANDS and RETAILERS (not individual bespoke tailors).
    """
    llm = get_llm(fast=True)
    prompt = f"""You are helping a Portuguese suit manufacturer find potential retail partners.

CITY: {city}
COUNTRY: {country}

Generate 8-10 search queries to find MEN'S SUIT BRANDS AND RETAILERS in {city}.

IMPORTANT RULES:
- We want BRANDS and RETAILERS that sell men's suits (ready-to-wear), NOT individual bespoke tailors
- We want businesses with physical stores (ideally 2-20 stores), not online-only
- Include queries in English AND the local language of {city}
- Focus on: suits, blazers, tailored jackets, formal menswear
- DO NOT focus on: bespoke-only tailors, made-to-measure-only ateliers, shirt-only shops
- Mix different angles: "men's suit brand", "menswear retailer", "formal wear store", "suit shop"

GOOD query examples:
- "men's suit brands {city} retailer"
- "premium menswear store {city} suits"
- "formal wear brand {city} multiple locations"
- "{city} men's clothing store suits jackets"

BAD query examples (too narrow):
- "bespoke tailor {city}" (finds only individual tailors)
- "custom suit {city}" (finds only made-to-measure)
- "Savile Row style {city}" (too luxury/niche)

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
        f"men's suit brands {city} retailer",
        f"premium menswear store {city} suits jackets",
        f"formal wear brand {city} {country}",
        f"{city} men's clothing store suits",
        f"best suit shops {city} {country}",
        f"menswear retailer {city} multiple stores",
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

    progress = [f"🚀 Pipeline iniciado para {target_city}"]

    # 1. Infer country
    target_country = await _infer_country(target_city)
    logger.info("País inferido: %s → %s", target_city, target_country)
    progress.append(f"🌍 País: {target_country}")

    # 2. Exchange rate (for downstream price conversion)
    exchange_rate = await get_exchange_rate()

    # 3. Generate queries via LLM
    t_queries = step_begin(logger, "N1a_QUERIES", target_city,
                           "Gerar queries de pesquisa com LLM.")
    queries = await _generate_queries(target_city, target_country)
    step_end(logger, "N1a_QUERIES", target_city, t_queries, queries=len(queries))

    for i, q in enumerate(queries):
        logger.info("  Query %d: %s", i + 1, q)
        progress.append(f"  🔎 Q{i+1}: \"{q}\"")

    progress.append(f"✅ {len(queries)} queries geradas")

    # 4. Call Exa for each query
    exa = Exa(api_key=os.environ.get("EXA_API_KEY"))
    all_raw: List[Dict] = []

    t_exa = step_begin(logger, "N1b_EXA_SEARCH", target_city,
                        f"Executar {len(queries)} queries no Exa.")

    for i, query in enumerate(queries):
        try:
            exa_kwargs = {
                "num_results": EXA_NUM_RESULTS,
                "type": "auto",
                "exclude_domains": EXCLUDE_DOMAINS,
                "contents": {"text": {"maxCharacters": 10000}, "highlights": True},
            }
            response = await _exa_search_with_retries(exa, query, exa_kwargs)

            for result in response.results:
                url = result.url or ""
                if not url:
                    continue
                text_content = result.text if hasattr(result, "text") and result.text else ""
                highlights = " ".join(result.highlights) if hasattr(result, "highlights") and result.highlights else ""
                all_raw.append({
                    "url": url,
                    "title": result.title or "",
                    "text": text_content,
                    "highlights": highlights,
                })

            logger.info("  Exa Q%d: %d results", i + 1, len(response.results))
            progress.append(f"  ✓ Q{i+1}: {len(response.results)} resultados")

        except Exception as e:
            logger.error("  Exa Q%d failed: %s", i + 1, e)
            progress.append(f"  ⚠️ Q{i+1} falhou: {e}")

    step_end(logger, "N1b_EXA_SEARCH", target_city, t_exa,
             raw_results=len(all_raw))

    # 5. Deduplicate by domain
    unique_results = _deduplicate_by_domain(all_raw)
    logger.info("Dedup: %d raw → %d unique domains", len(all_raw), len(unique_results))
    progress.append(f"📈 {len(all_raw)} brutos → {len(unique_results)} domínios únicos")

    step_end(logger, "N1_DISCOVERY", target_city, t_node,
             queries=len(queries), unique_domains=len(unique_results))

    return {
        "target_country": target_country,
        "exchange_rate": exchange_rate,
        "search_results_raw": unique_results,
        "progress": progress,
    }
