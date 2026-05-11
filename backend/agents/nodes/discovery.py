"""
Node 2: Discovery Node
Performs web searches using Exa (neural/semantic search) and finds potential brand URLs.
Supports multilingual queries with per-language Exa parameter tuning.
"""
import asyncio
import logging
import os
from typing import List, Dict, Any, Union, Tuple
from urllib.parse import urlparse
from models import ProspectorState, QuerySearchResults
from .utils import normalize_url
from exa_py import Exa

logger = logging.getLogger("node.discovery")

# Configurable override (English only): default auto + company per Exa hybrid rules.
EXA_EN_SEARCH_TYPE = os.environ.get("EXA_EN_SEARCH_TYPE", "auto")
EXA_NUM_RESULTS = int(os.environ.get("EXA_NUM_RESULTS", "20"))
EXA_MAX_RETRIES = int(os.environ.get("EXA_MAX_RETRIES", "3"))
EXA_RETRY_INITIAL_SEC = float(os.environ.get("EXA_RETRY_INITIAL_SEC", "1.5"))


def _exa_transient(exc: BaseException) -> bool:
    """True when the failure may succeed on retry or with different Exa params."""
    s = str(exc).lower()
    needles = (
        "500",
        "502",
        "503",
        "504",
        "429",
        "internal_error",
        "try again",
        "timeout",
        "timed out",
        "connection reset",
        "temporarily",
    )
    return any(n in s for n in needles)


async def _exa_search_with_retries(
    exa: Exa,
    query: str,
    exa_kwargs: Dict[str, Any],
) -> Any:
    """Run sync exa.search in a thread with exponential backoff on transient errors."""
    last: BaseException = RuntimeError("exa search failed")
    for attempt in range(EXA_MAX_RETRIES):
        try:
            return await asyncio.to_thread(exa.search, query, **exa_kwargs)
        except BaseException as e:
            last = e
            if attempt + 1 < EXA_MAX_RETRIES and _exa_transient(e):
                wait = EXA_RETRY_INITIAL_SEC * (2 ** attempt)
                logger.warning(
                    "│   Exa transient error (attempt %s/%s): %s — retry in %.1fs",
                    attempt + 1,
                    EXA_MAX_RETRIES,
                    e,
                    wait,
                )
                await asyncio.sleep(wait)
            else:
                break
    raise last


def _contents_kwargs() -> Dict[str, Any]:
    return {"text": {"maxCharacters": 10000}, "highlights": True}


async def _run_one_exa_query(
    exa: Exa,
    query: str,
    exclude_domains: List[str],
    lang: str,
) -> Tuple[Any, str, str, str]:
    """
    Returns (response, search_type, category_label, mode_note).
    mode_note is empty or describes fallback.
    """
    if lang == "en":
        primary = {
            "num_results": EXA_NUM_RESULTS,
            "type": EXA_EN_SEARCH_TYPE,
            "exclude_domains": exclude_domains,
            "contents": _contents_kwargs(),
        }
        # category=company is only valid with types like "auto", not with "keyword".
        if EXA_EN_SEARCH_TYPE != "keyword":
            primary["category"] = "company"
        cat_label_primary = "company" if "category" in primary else "none"
        try:
            resp = await _exa_search_with_retries(exa, query, primary)
            return resp, EXA_EN_SEARCH_TYPE, cat_label_primary, ""
        except BaseException as prim_err:
            if primary.get("type") == "keyword" and "category" not in primary:
                raise prim_err
            logger.warning(
                "│   EN search failed (%s); fallback type=keyword category=none",
                prim_err,
            )
            fallback: Dict[str, Any] = {
                "num_results": EXA_NUM_RESULTS,
                "type": "keyword",
                "exclude_domains": exclude_domains,
                "contents": _contents_kwargs(),
            }
            resp = await _exa_search_with_retries(exa, query, fallback)
            return resp, "keyword", "none", " (fallback after EN primary failure)"

    local: Dict[str, Any] = {
        "num_results": EXA_NUM_RESULTS,
        "type": "keyword",
        "exclude_domains": exclude_domains,
        "contents": _contents_kwargs(),
    }
    resp = await _exa_search_with_retries(exa, query, local)
    return resp, "keyword", "none", ""


def deduplicate_by_domain(urls_with_data: List[Dict]) -> List[Dict]:
    """Dedup raw Exa results by root domain, keeping first occurrence."""
    seen = set()
    unique = []
    for item in urls_with_data:
        url = item.get("url", "")
        domain = urlparse(url).netloc.lower().replace("www.", "")
        if domain and domain not in seen:
            seen.add(domain)
            unique.append(item)
    return unique


async def discovery_node(state: Union[ProspectorState, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Discovery — Find potential brand URLs using Exa.
    6-9 queries × 15-20 results each → ~120-180 raw → ~80-120 after domain dedup.
    """
    search_queries = state.search_queries if hasattr(state, "search_queries") else state.get("search_queries", [])
    query_origins = state.query_origins if hasattr(state, "query_origins") else state.get("query_origins", [])
    query_languages = state.get("query_languages", []) if isinstance(state, dict) else getattr(state, "query_languages", [])

    logger.info("┌─── NODE 2: DISCOVERY ─────────────────────────────")
    logger.info("│ Queries to execute: %d", len(search_queries))

    all_raw_results: List[Dict] = []
    search_results: List[QuerySearchResults] = []
    new_progress = []

    try:
        new_progress.append(f"🔍 Iniciando busca com {len(search_queries)} queries...")

        exa = Exa(api_key=os.environ.get("EXA_API_KEY"))
        exclude_domains = [
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

        raw_count = 0
        per_query_unique = []
        seen_domains_running = set()

        for i, query in enumerate(search_queries):
            origin = query_origins[i] if i < len(query_origins) else "Unknown"
            lang = query_languages[i] if i < len(query_languages) else "en"
            try:
                logger.info(
                    "│ [Exa] Query %d/%d (%s) [%s] starting: \"%s\"",
                    i + 1,
                    len(search_queries),
                    origin,
                    lang,
                    query,
                )
                new_progress.append(f"🔎 Query {i + 1} [{lang}]: \"{query}\"")

                response, search_type, category_label, mode_note = await _run_one_exa_query(
                    exa, query, exclude_domains, lang
                )
                logger.info(
                    "│ [Exa] Query %d/%d (%s) [%s] type=%s category=%s%s: \"%s\"",
                    i + 1,
                    len(search_queries),
                    origin,
                    lang,
                    search_type,
                    category_label,
                    mode_note,
                    query,
                )

                query_results = QuerySearchResults(
                    query_index=i, query=query, query_origin=origin, results=[]
                )
                query_new_domains = 0
                for result in response.results:
                    url = result.url or ""
                    if not url:
                        continue
                    raw_count += 1
                    highlights_str = " ".join(result.highlights) if hasattr(result, "highlights") and result.highlights else ""
                    text_content = result.text if hasattr(result, "text") and result.text else ""

                    domain = urlparse(url).netloc.lower().replace("www.", "")
                    if domain and domain not in seen_domains_running:
                        seen_domains_running.add(domain)
                        query_new_domains += 1

                    item = {
                        "url": url,
                        "title": result.title or "",
                        "content": highlights_str,
                        "text": text_content,
                        "query_origin": origin,
                    }
                    all_raw_results.append(item)
                    query_results.results.append(item)

                search_results.append(query_results)
                per_query_unique.append(query_new_domains)
                logger.info("│   → %d results | %d new unique domains | query=%s | language=%s | numResults=%d | unique_after_dedup=%d",
                            len(response.results), query_new_domains, query, lang, EXA_NUM_RESULTS, query_new_domains)
                new_progress.append(f"   ✓ {len(response.results)} resultados ({query_new_domains} novos)")
            except Exception as e:
                logger.error("│   → Query %d FAILED: %s", i + 1, e)
                new_progress.append(f"   ⚠️ Query {i + 1} falhou")
                per_query_unique.append(0)

        unique_results = deduplicate_by_domain(all_raw_results)
        candidate_urls = [r["url"] for r in unique_results]

        logger.info("│ Raw results: %d → After domain dedup: %d", raw_count, len(candidate_urls))
        new_progress.append(
            f"📈 {raw_count} brutos → {len(candidate_urls)} URLs únicos (dedup por domínio)"
        )

        for i, url in enumerate(candidate_urls[:10]):
            logger.info("│   URL %d: %s", i + 1, url)
        if len(candidate_urls) > 10:
            logger.info("│   ... and %d more", len(candidate_urls) - 10)
        logger.info("└──────────────────────────────────────────────────")

        return {
            "candidate_urls": candidate_urls,
            "search_results": search_results,
            "progress": new_progress,
        }
    except Exception as error:
        return {
            "error": str(error),
            "progress": new_progress + ["❌ Descoberta falhou"],
        }
