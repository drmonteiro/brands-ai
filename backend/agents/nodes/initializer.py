"""
Node 1: Search Initializer
Generates search queries and handles initial setup/cache checking.
"""
from typing import List, Dict, Any, Union
from models import ProspectorState
from services.database import get_prospects_by_city
from .utils import get_exchange_rate, convert_eur_to_usd

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
        if any(c in city_lower for c in ["london", "manchester", "birmingham"]): target_country = "UK"
        elif any(c in city_lower for c in ["paris", "lyon", "marseille"]): target_country = "France"
        elif any(c in city_lower for c in ["berlin", "munich", "hamburg", "frankfurt"]): target_country = "Germany"
        elif any(c in city_lower for c in ["milan", "rome", "florence", "naples"]): target_country = "Italy"
        elif any(c in city_lower for c in ["madrid", "barcelona"]): target_country = "Spain"
        elif any(c in city_lower for c in ["lisbon", "porto"]): target_country = "Portugal"
    
    print(f"[INIT] Starting intelligent search for: {target_city}, {target_country}")
    
    # 💰 CACHE CHECK
    existing_prospects = await get_prospects_by_city(target_city, limit=100)
    
    if len(existing_prospects) >= 10:
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
    
    # Generate queries (Optimized to avoid unnecessary LLM call for standard search patterns)
    search_queries = generate_queries_from_clients(target_city)
    
    new_progress = [
        f"🚀 Pesquisa iniciada para {target_city}. Preço alvo: ${price_threshold_usd:.0f}",
        "🔍 A gerar queries inteligentes baseadas no perfil ideal da Lança...",
        f"✅ {len(search_queries)} queries geradas pelo agente de análise"
    ]
    
    for idx, query in enumerate(search_queries):
        new_progress.append(f"   Query {idx + 1}: \"{query}\"")
    
    return {
        "exchange_rate": exchange_rate,
        "price_threshold_usd": price_threshold_usd,
        "search_queries": search_queries,
        "progress": new_progress,
        "search_results": [], # Initialize empty list for results
    }

def generate_queries_from_clients(target_city: str) -> List[str]:
    """
    Generate search queries based on Confeções Lança's ideal client profile.
    
    COST OPTIMIZATION: Uses hardcoded query templates instead of LLM call.
    These templates are proven effective patterns based on Lança's ideal client profile.
    """
    queries = [
        f"{target_city} luxury menswear boutique premium suits",
        f"{target_city} bespoke tailor custom suits high end",
        f"{target_city} designer men suits store independent",
        f"{target_city} sastreria a medida fatos de cerimónia wedding suits store",
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
