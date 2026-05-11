"""
Query Builder for Confeções Lança Prospector

Config-driven query generation with multilingual support.
Uses templates from data.query_templates and LLM-based language inference.
"""
import logging
import json
from typing import Dict, List, Tuple
from data.query_templates import build_queries_for_city

logger = logging.getLogger("services.query_builder")

# LLM language inference cache (per process); city map hits skip LLM entirely.
_llm_lang_cache: Dict[str, List[str]] = {}


# ============================================================================
# ENGLISH-SPEAKING CITIES (no local-language query generation needed)
# ============================================================================

ENGLISH_CITIES = {
    "london", "manchester", "birmingham", "edinburgh", "glasgow", "liverpool",
    "bristol", "leeds", "sheffield", "nottingham", "cardiff", "belfast",
    "new york", "los angeles", "chicago", "boston", "san francisco", "miami",
    "washington", "seattle", "dallas", "houston", "philadelphia", "atlanta",
    "sydney", "melbourne", "toronto", "vancouver", "dublin",
}


def is_english_city(city: str) -> bool:
    """Check if a city is in an English-speaking country."""
    return city.lower().strip() in ENGLISH_CITIES


# ============================================================================
# LANGUAGE INFERENCE
# ============================================================================

async def infer_city_languages(city: str) -> List[str]:
    """
    Primary language(s) for commerce in `city` (ISO 639-1).

    Order: hardcoded English cities → static city map (~50+ metros) → LLM (cached).
    """
    if is_english_city(city):
        return ["en"]

    from data.city_language_map import lookup_city_languages

    key = city.lower().strip()
    mapped = lookup_city_languages(city)
    if mapped is not None:
        logger.info("Languages for %s (city map): %s", city, mapped)
        return mapped

    if key in _llm_lang_cache:
        logger.info("Languages for %s (LLM cache): %s", city, _llm_lang_cache[key])
        return _llm_lang_cache[key]

    from agents.nodes.utils import get_llm
    llm = get_llm(fast=True, temperature=0.0)
    prompt = f"""Given the city '{city}', what are the primary language(s) used for commerce there?

Return ONLY a JSON array of ISO 639-1 language codes. For bilingual cities, return both.
Examples:
- "Milano" → ["it"]
- "Paris" → ["fr"]
- "Brussels" → ["fr", "nl"]
- "Barcelona" → ["es", "ca"]
- "Montreal" → ["fr", "en"]
- "Zürich" → ["de"]
- "Tokyo" → ["ja"]
- "London" → ["en"]

Return ONLY the JSON array, no explanation."""

    try:
        response = await llm.ainvoke(prompt)
        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        languages = json.loads(raw)
        if isinstance(languages, list) and all(isinstance(l, str) for l in languages):
            logger.info("Languages for %s (LLM): %s", city, languages)
            _llm_lang_cache[key] = languages
            return languages
    except Exception as e:
        logger.warning("Language inference failed for %s: %s", city, e)

    return ["en"]


# ============================================================================
# QUERY GENERATION (main entry point)
# ============================================================================

async def select_queries(
    city: str,
    languages: List[str] = None,
) -> Tuple[List[str], List[str], List[str]]:
    """
    Generate 6-9 search queries for a city using config-driven templates.

    - Always 3 English queries
    - 3 per local language (if not English)
    - For multilingual cities: up to 3 more in secondary language

    Returns:
        (queries, origins, languages) — parallel lists.
    """
    if languages is None:
        languages = await infer_city_languages(city)

    query_dicts = build_queries_for_city(city, languages)

    queries = [q["query"] for q in query_dicts]
    origins = [q["origin"] for q in query_dicts]
    langs = [q["language"] for q in query_dicts]

    logger.info("Generated %d queries for %s (languages: %s)", len(queries), city, languages)
    for q, o, l in zip(queries, origins, langs):
        logger.info("  [%s] [%s] %s", o, l, q)

    return queries, origins, langs


# ============================================================================
# LEGACY SUPPORT — generate_local_queries (used by old code paths)
# ============================================================================

async def generate_local_queries(city: str) -> List[str]:
    """
    Legacy function: generates local-language queries via LLM.
    Kept for backward compatibility. New code should use select_queries().
    """
    if is_english_city(city):
        return []

    from agents.nodes.utils import get_llm
    llm = get_llm(fast=True, temperature=0.3)

    prompt = f"""You are a search query generator for a Portuguese suit manufacturer looking for retail partners.

CITY: {city}

TASK: Generate exactly 3 search queries in the LOCAL LANGUAGE of {city} to find independent menswear boutiques that sell tailored suits, trousers, jackets and waistcoats in the mid-to-high price range (€500-€1700).

RULES:
1. Detect which language is most commonly used for commerce in {city}
2. If {city} is in an English-speaking country, return an empty array []
3. Write queries that a local person would actually type into Google to find suit shops
4. Include the city name in each query
5. Focus on: independent boutiques, tailored suits, mid-range pricing, own brand/label collections
6. Do NOT target ultra-luxury/bespoke ateliers or fast fashion chains

Return ONLY a JSON array of 3 strings. No explanation."""

    try:
        response = await llm.ainvoke(prompt)
        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        queries = json.loads(raw)
        if isinstance(queries, list) and all(isinstance(q, str) for q in queries):
            return queries[:3]
        return []
    except Exception as e:
        logger.warning("Local query generation failed for %s: %s", city, e)
        return []
