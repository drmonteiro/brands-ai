"""
Node 1: Search Initializer
Generates search queries and handles initial setup/cache checking.
Uses LLM (mini) to generate local-language queries for any city in the world.
"""
from typing import List, Dict, Any, Union
import json
from models import ProspectorState
from services.database import get_prospects_by_city
from .utils import get_exchange_rate, convert_eur_to_usd, get_llm


# ============================================================================
# ENGLISH-SPEAKING CITIES (skip local query generation for these)
# ============================================================================

ENGLISH_SPEAKING_COUNTRIES = {"uk", "us", "usa", "australia", "canada", "ireland", "new zealand"}
ENGLISH_CITIES = {
    "london", "manchester", "birmingham", "edinburgh", "glasgow", "liverpool",
    "bristol", "leeds", "sheffield", "nottingham", "cardiff", "belfast",
    "new york", "los angeles", "chicago", "boston", "san francisco", "miami",
    "washington", "seattle", "dallas", "houston", "philadelphia", "atlanta",
    "sydney", "melbourne", "toronto", "vancouver", "dublin",
}


def is_english_city(city: str) -> bool:
    """Check if a city is in an English-speaking country (no need for local queries)."""
    return city.lower().strip() in ENGLISH_CITIES


async def generate_local_queries(city: str) -> List[str]:
    """
    Uses GPT-5.1-mini (~$0.01) to generate 2-3 search queries in the local language
    of the city. Works for ANY city in the world without hardcoded mappings.
    
    Returns empty list for English-speaking cities.
    """
    if is_english_city(city):
        return []
    
    llm = get_llm(fast=True, temperature=0.3)  # mini model — cheap and fast
    
    prompt = f"""You are a search query generator for a Portuguese suit manufacturer looking for retail partners.

CITY: {city}

TASK: Generate exactly 3 search queries in the LOCAL LANGUAGE of {city} to find independent menswear boutiques that sell tailored suits, trousers, jackets and waistcoats in the mid-to-high price range (€500-€1700).

RULES:
1. Detect which language is most commonly used for commerce in {city} (e.g., Italian for Milano, French for Paris, German for Berlin, Japanese for Tokyo, etc.)
2. If {city} is in an English-speaking country, return an empty array []
3. Write queries that a local person would actually type into Google to find suit shops
4. Include the city name in each query
5. Focus on: independent boutiques, tailored suits, mid-range pricing, own brand/label collections
6. Do NOT target ultra-luxury/bespoke ateliers or fast fashion chains

EXAMPLES:
- Milano → ["Milano negozio abiti uomo sartoriale classico", "Milano boutique moda uomo indipendente", "Milano sartoria abiti pronti marca propria"]
- Paris → ["Paris boutique costume homme tailleur prêt-à-porter", "Paris magasin mode masculine indépendant", "Paris costume sur mesure prix moyen"]
- Berlin → ["Berlin Herrenmode Anzüge maßgeschneidert Boutique", "Berlin Herrenbekleidung Anzug unabhängig", "Berlin Herrenanzug Premium Eigenmarke"]

Return ONLY a JSON array of 3 strings. No explanation."""

    try:
        response = await llm.ainvoke(prompt)
        raw = response.content.strip()
        # Clean markdown fences if the model wraps in ```json
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        
        queries = json.loads(raw)
        
        # Validate: must be a list of strings
        if isinstance(queries, list) and all(isinstance(q, str) for q in queries):
            print(f"[INIT] 🌍 Generated {len(queries)} local queries for {city}")
            for q in queries:
                print(f"   → {q}")
            return queries[:3]  # cap at 3
        
        return []
    except Exception as e:
        print(f"[INIT] ⚠️ Local query generation failed for {city}: {e}")
        # Fallback: return empty — the English queries will still work
        return []


async def infer_country(city: str) -> str:
    """Use fast LLM to dynamically identify the country of a given city."""
    try:
        llm = get_llm(fast=True, temperature=0.0)
        prompt = f"Given the city '{city}', what country is it in? Reply with ONLY the English name of the country. No punctuation. Example: if city is 'Milano', reply 'Italy'."
        response = await llm.ainvoke(prompt)
        return response.content.strip()
    except Exception as e:
        print(f"[INIT] Warning: Failed to infer country for {city} via LLM: {e}")
        return "USA"  # Fallback

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
        inferred_country = await infer_country(target_city)
        if inferred_country:
            target_country = inferred_country
    
    print(f"[INIT] Starting intelligent search for: {target_city}, {target_country}")
    
    # 💰 CACHE CHECK
    existing_prospects = await get_prospects_by_city(target_city, limit=100)
    force_refresh = state.get("force_refresh", False) if isinstance(state, dict) else getattr(state, "force_refresh", False)
    
    if len(existing_prospects) >= 25 and not force_refresh:
        return {
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
    
    # Fetch current exchange rate
    exchange_rate = await get_exchange_rate()
    price_threshold_usd = convert_eur_to_usd(price_threshold_eur, exchange_rate)
    
    # DYNAMIC QUERY GENERATION
    search_queries, query_origins = await select_queries(target_city)
    
    new_progress = [
        f"🚀 Pesquisa iniciada para {target_city}. Preço alvo: ${price_threshold_usd:.0f}",
        "🔍 A gerar queries inteligentes...",
        f"✅ {len(search_queries)} queries geradas"
    ]
    
    for idx, (query, origin) in enumerate(zip(search_queries, query_origins)):
        new_progress.append(f"   [{origin}] \"{query}\"")
    
    return {
        "exchange_rate": exchange_rate,
        "price_threshold_usd": price_threshold_usd,
        "search_queries": search_queries,
        "query_origins": query_origins,
        "progress": new_progress,
        "search_results": [],
    }

async def select_queries(city: str) -> tuple[List[str], List[str]]:
    """
    Generates 6-9 optimized search queries:
    - 6 fixed English queries (core axes)
    - 0-3 local language queries (generated by LLM mini, ~$0.01)
    """
    selected_queries = []
    origins = []
    
    # === ENGLISH QUERIES (always present) ===
    
    # 1. Sartorial — core tailored menswear
    selected_queries.append(f"{city} independent menswear brands tailored suits shop")
    origins.append("Sartorial")
    
    # 2. RTW / Own Label — ready-to-wear focus
    selected_queries.append(f"{city} suit shop ready to wear own label collection")
    origins.append("RTW/Label")
    
    # 3. Wedding / Occasion
    selected_queries.append(f"{city} wedding suits formalwear boutique affordable")
    origins.append("Wedding")
    
    # 4-5. Editorial / Top Lists — most efficient queries
    selected_queries.append(f"best tailored suits shop in {city}")
    origins.append("Editorial")
    selected_queries.append(f"top menswear boutiques in {city}")
    origins.append("Editorial")
    
    # 6. Catch-all
    selected_queries.append(f"{city} men's suits mid range affordable premium boutique")
    origins.append("Catch-all")
    
    # 7. B2B / Private Label — directly targets brands seeking manufacturing partners
    selected_queries.append(f"{city} menswear brand private label own brand collection suits")
    origins.append("B2B/PrivateLabel")
    
    # 8. Trade / Wholesale — finds brands through industry channels
    selected_queries.append(f"{city} independent suit brand wholesale stockist retailer")
    origins.append("Trade")
    
    # 9. Emerging Brands — new entrants actively building supply chains
    selected_queries.append(f"new menswear brand {city} tailored suits launch")
    origins.append("Emerging")
    
    # === LOCAL LANGUAGE QUERIES (LLM mini, ~$0.01) ===
    local_queries = await generate_local_queries(city)
    if local_queries:
        selected_queries.extend(local_queries)
        origins.extend([f"Local Language"] * len(local_queries))
    
    return selected_queries, origins


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
