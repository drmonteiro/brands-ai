"""
Node 1: Search Initializer
Generates search queries and handles initial setup/cache checking.
"""
from typing import List, Dict, Any, Union
from models import ProspectorState
from services.database import get_prospects_by_city
from .utils import get_exchange_rate, convert_eur_to_usd

import random
from .utils import get_llm

async def initialize_search(state: Union[ProspectorState, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Initialize search and generate queries using optimized templates based on ideal client profile.
    """
    # Handle both object and dict state
    target_city = state.target_city if hasattr(state, "target_city") else state.get("target_city")
    target_country = state.target_country if hasattr(state, "target_country") else state.get("target_country", "USA")
    price_threshold_eur = state.price_threshold_eur if hasattr(state, "price_threshold_eur") else state.get("price_threshold_eur", 500)
    
    # [V2.5] Basic Country Inference
    if target_country == "USA": # Only try to infer if it's the default
        city_lower = target_city.lower()
        if any(c in city_lower for f, c in [("london", "london"), ("manchester", "manchester"), ("birmingham", "birmingham")]): target_country = "UK"
        elif any(c in city_lower for c in ["paris", "lyon", "marseille"]): target_country = "France"
        elif any(c in city_lower for c in ["berlin", "munich", "hamburg", "frankfurt"]): target_country = "Germany"
        elif any(c in city_lower for c in ["milan", "rome", "florence", "naples"]): target_country = "Italy"
        elif any(c in city_lower for c in ["madrid", "barcelona"]): target_country = "Spain"
        elif any(c in city_lower for c in ["lisbon", "porto"]): target_country = "Portugal"
    
    # [V2.7] Tier Detection
    tier1_cities = ["London", "Paris", "Milan", "New York", "Boston", "Madrid", "Lisbon", "Tokyo", "Hong Kong", "Zurich"]
    tier = 1 if any(t.lower() in target_city.lower() for t in tier1_cities) else 2
    
    print(f"[INIT] Starting intelligent search for: {target_city}, {target_country} (Tier {tier})")
    
    # 💰 CACHE CHECK
    existing_prospects = await get_prospects_by_city(target_city, limit=100)
    force_refresh = state.get("force_refresh", False) if isinstance(state, dict) else getattr(state, "force_refresh", False)
    
    if len(existing_prospects) >= 10 and not force_refresh:
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
    
    # [V2.7] DYNAMIC QUERY GENERATION
    search_queries, query_origins = await select_queries(target_city, target_country, tier)
    
    new_progress = [
        f"🚀 Pesquisa iniciada para {target_city} (Tier {tier}). Preço alvo: ${price_threshold_usd:.0f}",
        "🔍 A gerar queries inteligentes segmentadas por eixos...",
        f"✅ {len(search_queries)} queries geradas (Mix de qualidade, B2B e local)"
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
        "tier": tier
    }

async def select_queries(city: str, country: str, tier: int) -> tuple[List[str], List[str]]:
    """
    Selects 4-6 optimized queries based on 5 strategic axes.
    """
    # Eixo 1 - Qualidade técnica (Tailored, mid-to-high range)
    eixo1 = [
        f"{city} men's suits tailored fit shop under £1700",
        f"{city} half canvas made-to-measure menswear boutique",
        f"{city} sartorial menswear suits slim fit tailored",
        f"{city} independent menswear brands tailored suits slim fit"
    ]
    
    # Eixo 2 - Tecidos Premium (mid-high range)
    eixo2 = [
        f"{city} Vitale Barberis Canonico Cerruti suits tailor boutique",
        f"{city} quality wool suits menswear store mid range",
        f"{city} suit shop ready to wear tailoring own label collection jackets trousers"
    ]
    
    # Eixo 3 - Canal B2B e Private Label
    eixo3 = [
        f"{city} private label suits menswear wholesale",
        f"{city} white label menswear manufacturer partner boutique",
        f"{city} own label collection suits menswear store"
    ]
    
    # Eixo 4 - Cerimónia e Ocasião
    eixo4 = [
        f"{city} wedding suits formalwear boutique affordable",
        f"{city} formal menswear trousers waistcoats wedding suits",
        f"{city} menswear store suits waistcoats trousers smart casual"
    ]
    
    # Editorial Axis (mid-high range focus)
    eixo_editorial = [
        f"best tailored suits shop in {city}",
        f"top menswear boutiques in {city}",
        f"best men's suits in {city} mid range",
        f"men's tailored suits {city} mid range affordable"
    ]

    # Dynamically generate local language query (Axis 5)
    axis5_query = await generate_local_query(city, country)
    
    selected_queries = []
    origins = []
    
    if tier == 1:
        # Tier 1: ~14 queries (maximized for coverage)
        selected_queries.extend(random.sample(eixo1, 3))
        origins.extend(["Axis 1 (Sartorial)"] * 3)
        
        selected_queries.extend(eixo2)  # All 3
        origins.extend(["Axis 2 (Fabrics)"] * len(eixo2))
        
        selected_queries.extend(random.sample(eixo3, 2))
        origins.extend(["Axis 3 (B2B/Label)"] * 2)
        
        selected_queries.extend(eixo4)  # All 3
        origins.extend(["Axis 4 (Wedding)"] * len(eixo4))
        
        selected_queries.extend(random.sample(eixo_editorial, 3))
        origins.extend(["Axis Editorial"] * 3)
        
        selected_queries.append(axis5_query)
        origins.append("Axis 5 (Local)")
    else:
        # Tier 2: ~6 queries
        selected_queries.append(random.choice(eixo1))
        origins.append("Axis 1 (Sartorial)")
        
        selected_queries.append(random.choice(eixo3))
        origins.append("Axis 3 (B2B/Label)")
        
        selected_queries.append(random.choice(eixo4))
        origins.append("Axis 4 (Wedding)")
        
        selected_queries.append(random.choice(eixo_editorial))
        origins.append("Axis Editorial")
        
        selected_queries.append(axis5_query)
        origins.append("Axis 5 (Local)")
        
        # Add one more random from Axis 1 or 2
        extra = random.choice(eixo1 + eixo2)
        selected_queries.append(extra)
        origins.append("Axis Extra")


    return selected_queries, origins

async def generate_local_query(city: str, country: str) -> str:
    """Uses LLM to generate a local language search query for the city."""
    llm = get_llm()
    prompt = f"""
    Create a single search query in the local language of {city}, {country} to find mid-to-high range tailored menswear shops or independent suit boutiques (price range €500-€1700).
    Focus on tailored suits, trousers, jackets and waistcoats — NOT ultra-luxury or bespoke ateliers.
    Example for Milan: "Milano negozio abiti uomo su misura vestiti eleganti"
    Example for Paris: "Paris costume homme tailleur boutique prêt-à-porter"
    Return ONLY the query string.
    """
    try:
        response = await llm.ainvoke(prompt)
        return response.content.strip().strip('"')
    except:
        return f"{city} tailored suits menswear shop mid range"

def generate_queries_from_clients(target_city: str) -> List[str]:

    """
    Generate search queries based on Confeções Lança's ideal client profile.
    
    COST OPTIMIZATION: Uses hardcoded query templates instead of LLM call.
    These templates are proven effective patterns based on Lança's ideal client profile.
    """
    queries = [
        f"{target_city} menswear boutique tailored suits mid range",
        f"{target_city} tailored fit suits shop affordable premium",
        f"{target_city} men's suits store independent own label",
        f"{target_city} fatos de cerimónia wedding suits store",
    ]

    print(f"[QUERY-AGENT] Using optimized queries for {target_city} (4 queries)")
    for i, q in enumerate(queries, 1):
        print(f"   Query {i}: \"{q}\"")
    
    return queries

def create_initial_state(city: str) -> ProspectorState:
    """Create initial state for a new prospecting session."""
    return ProspectorState(
        target_city=city,
        target_country="USA", # Default, ideally derived later
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
