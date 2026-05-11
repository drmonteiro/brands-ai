"""
Node 1: Search Initializer
Generates search queries and handles initial setup/cache checking.
Uses LLM (mini) to generate local-language queries for any city in the world.
"""
import logging
from typing import List, Dict, Any, Union
from models import ProspectorState
from services.database import get_prospects_by_city
from services.query_builder import select_queries, infer_city_languages
from .utils import get_exchange_rate, convert_eur_to_usd, get_llm

logger = logging.getLogger("node.initializer")


async def infer_country(city: str) -> str:
    """Use fast LLM to dynamically identify the country of a given city."""
    try:
        llm = get_llm(fast=True, temperature=0.0)
        prompt = f"Given the city '{city}', what country is it in? Reply with ONLY the English name of the country. No punctuation. Example: if city is 'Milano', reply 'Italy'."
        response = await llm.ainvoke(prompt)
        return response.content.strip()
    except Exception as e:
        logger.warning("Failed to infer country for %s: %s — defaulting to USA", city, e)
        return "USA"

async def initialize_search(state: Union[ProspectorState, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Initialize search and generate queries using optimized templates + LLM local queries.
    """
    # Handle both object and dict state
    target_city = state.target_city if hasattr(state, "target_city") else state.get("target_city")
    target_country = state.target_country if hasattr(state, "target_country") else state.get("target_country", "USA")
    price_threshold_eur = state.price_threshold_eur if hasattr(state, "price_threshold_eur") else state.get("price_threshold_eur", 500)
    
    # [V2.5] Dynamic Country Inference via LLM (if missing or default USA)
    if target_country == "USA" or not target_country:
        logger.info("Inferring country for '%s' via LLM...", target_city)
        inferred_country = await infer_country(target_city)
        if inferred_country:
            target_country = inferred_country
            logger.info("Country inferred: %s → %s", target_city, target_country)
    
    logger.info("┌─── NODE 1: INITIALIZE ───────────────────────────")
    logger.info("│ City: %s | Country: %s", target_city, target_country)
    
    existing_prospects = await get_prospects_by_city(target_city, limit=100)
    force_refresh = state.get("force_refresh", False) if isinstance(state, dict) else getattr(state, "force_refresh", False)
    logger.info("│ Existing prospects in DB: %d | force_refresh: %s", len(existing_prospects), force_refresh)
    
    if len(existing_prospects) >= 25 and not force_refresh:
        logger.info("│ Cache sufficient (≥25 prospects) — skipping full pipeline")
        logger.info("└──────────────────────────────────────────────────")
        return {
            "target_country": target_country,
            "exchange_rate": await get_exchange_rate(),
            "price_threshold_usd": 0,
            "search_queries": [],
            "progress": [
                f"✅ {target_city} já pesquisada anteriormente",
                f"💾 {len(existing_prospects)} marcas encontradas em cache (custo: €0.00)"
            ],
            "cached": True,
            "cached_count": len(existing_prospects),
        }
    
    exchange_rate = await get_exchange_rate()
    price_threshold_usd = convert_eur_to_usd(price_threshold_eur, exchange_rate)
    logger.info("│ Exchange rate: %.4f | Price threshold: €%d → $%.0f", exchange_rate, price_threshold_eur, price_threshold_usd)
    
    logger.info("│ Inferring languages for %s...", target_city)
    city_languages = await infer_city_languages(target_city)
    logger.info("│ Languages: %s", city_languages)

    logger.info("│ Generating search queries...")
    search_queries, query_origins, query_languages = await select_queries(target_city, languages=city_languages)
    for q, o, lang in zip(search_queries, query_origins, query_languages):
        logger.info("│   [%s] [%s] %s", o, lang, q)
    logger.info("│ Total queries: %d", len(search_queries))
    logger.info("└──────────────────────────────────────────────────")
    
    new_progress = [
        f"🚀 Pesquisa iniciada para {target_city}. Preço alvo: ${price_threshold_usd:.0f}",
        f"🌍 Idiomas detectados: {', '.join(city_languages)}",
        "🔍 A gerar queries inteligentes...",
        f"✅ {len(search_queries)} queries geradas ({len(city_languages)} idiomas)"
    ]
    
    for query, origin, lang in zip(search_queries, query_origins, query_languages):
        new_progress.append(f"   [{origin}] [{lang}] \"{query}\"")
    
    return {
        "target_country": target_country,
        "exchange_rate": exchange_rate,
        "price_threshold_usd": price_threshold_usd,
        "search_queries": search_queries,
        "query_origins": query_origins,
        "query_languages": query_languages,
        "progress": new_progress,
        "search_results": [],
    }

def create_initial_state(city: str) -> ProspectorState:
    """Create initial state for a new prospecting session."""
    return ProspectorState(
        target_city=city,
        target_country="USA", # Default, derived later in initialize_search
        search_queries=[],
        candidate_urls=[],
        potential_brands=[],
        verified_brands=[],
        approval_status={},
        email_logs=[],
        exchange_rate=1.08,
        price_threshold_eur=500,
        price_threshold_usd=540,
        max_stores=20,
        progress=[],
        search_results=[],
    )
