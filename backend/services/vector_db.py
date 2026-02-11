"""
PostgreSQL Vector Database Service for Confeções Lança

This service ONLY handles:
1. Storing embeddings of 18 TOP Lança clients (PERMANENT) using pgvector
2. Calculating similarity scores for prospects (TEMPORARY embeddings)
3. Prioritizing SMALL boutiques over large chains (Lança strategy)

IMPORTANT: Prospects are NOT stored here (see database.py)
"""

import os
import json
from typing import List, Dict, Optional, Tuple
from langchain_openai import AzureOpenAIEmbeddings, AzureChatOpenAI

from config import Config
from data.lanca_clients import (
    LANCA_CLIENTS,
    MARKET_STRENGTH_STATIC,
    IDEAL_CLIENT_PROFILE,
    get_top_clients,
)
from .postgres import PostgresManager

# ============================================================================
# VECTOR DATABASE SETUP (PostgreSQL + pgvector)
# ============================================================================

def get_azure_embeddings() -> AzureOpenAIEmbeddings:
    """Get Azure OpenAI embeddings function"""
    return AzureOpenAIEmbeddings(
        azure_endpoint=Config.AZURE_OPENAI_ENDPOINT,
        api_key=Config.AZURE_OPENAI_API_KEY,
        api_version=Config.AZURE_OPENAI_API_VERSION,
        azure_deployment=Config.AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
    )


# ============================================================================
# CLIENT PROFILE GENERATION (for embeddings)
# ============================================================================

def generate_client_profile_text(client: Dict) -> str:
    """
    Generate a rich text description of a client for embedding.
    """
    name = client.get("name", "Unknown")
    country = client.get("country", "Unknown")
    city = client.get("city", None)
    years = client.get("years_as_client", None)
    brand_type = client.get("brand_type", "unknown")
    
    # Location text
    location_text = f"{city}, {country}" if city and city != country else country
    
    # Price
    pvp = client.get("pvp_suits_eur", None)
    price_text = f"suits priced at €{pvp}" if pvp else "price not public"
    
    # Stores
    stores = client.get("store_count", 0)
    if stores <= 5: store_text = "small boutique"
    elif stores <= 20: store_text = "medium chain"
    else: store_text = "large chain"
    
    profile = f"{name} is a menswear brand from {location_text}. They are a {store_text} selling {price_text}."
    if brand_type != "unknown": profile += f" Business type: {brand_type}."
    
    return profile


# ============================================================================
# POPULATE DATABASE
# ============================================================================

async def populate_clients_database(force_refresh: bool = False) -> Dict:
    """
    Generate embeddings for all top Lança clients and store in PostgreSQL.
    """
    print("[VECTOR-DB] Starting to populate clients database...")
    
    pool = await PostgresManager.get_pool()
    embeddings_fn = get_azure_embeddings()
    
    async with pool.acquire() as conn:
        existing = await conn.fetchval("SELECT COUNT(*) FROM lanca_clients")
        if existing >= len(LANCA_CLIENTS) and not force_refresh:
            return {"status": "already_populated", "count": existing}
        
        if force_refresh:
            await conn.execute("DELETE FROM lanca_clients")
        
        for idx, client in enumerate(LANCA_CLIENTS):
            profile_text = generate_client_profile_text(client)
            embedding = await embeddings_fn.aembed_query(profile_text)
            
            await conn.execute("""
                INSERT INTO lanca_clients (
                    id, name, country, country_code, city,
                    store_count, brand_style, business_model,
                    profile_text, embedding
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    profile_text = EXCLUDED.profile_text,
                    embedding = EXCLUDED.embedding
            """,
                f"client_{idx}", client.get("name", "Unknown"),
                client.get("country", "Unknown"), client.get("country_code", "XX"),
                client.get("city", ""), int(client.get("store_count", 0)),
                str(client.get("brand_style", "unknown")), str(client.get("business_model", "unknown")),
                profile_text, str(embedding)
            )
    
    return {"status": "success", "count": len(LANCA_CLIENTS)}
async def find_similar_clients(
    prospect_description: str,
    n_results: int = 10,
    filter_metadata: Optional[Dict] = None,
) -> List[Dict]:
    """
    Find the most similar Lança clients using pgvector.
    """
    pool = await PostgresManager.get_pool()
    embeddings_fn = get_azure_embeddings()
    
    # Generate TEMPORARY embedding
    embedding = await embeddings_fn.aembed_query(prospect_description)
    
    async with pool.acquire() as conn:
        # Check if empty
        count = await conn.fetchval("SELECT COUNT(*) FROM lanca_clients")
        if count == 0:
            await populate_clients_database()
            
        # Vector similarity search using cosine distance (<=>)
        rows = await conn.fetch(f"""
            SELECT *, 1 - (embedding <=> $1::vector) as similarity_score
            FROM lanca_clients
            ORDER BY embedding <=> $1::vector
            LIMIT $2
        """, str(embedding), n_results)
        
        similar_clients = []
        for row in rows:
            # Convert record to dict and handle metadata structure
            client_dict = dict(row)
            similarity = client_dict.pop('similarity_score')
            
            similar_clients.append({
                "id": client_dict['id'],
                "name": client_dict['name'],
                "country": client_dict['country'],
                "similarity": round(similarity * 100, 2),
                "metadata": client_dict,
                "profile": client_dict['profile_text'],
            })
            
    return similar_clients


# ============================================================================
# SIMILARITY EXPLANATION GENERATION
# ============================================================================

async def generate_similarity_explanation(
    prospect: Dict,
    similar_client: Dict,
    similarity_score: float
) -> str:
    """
    Generate a human-readable explanation of why a prospect is similar to a Lança client.
    Uses LLM to compare characteristics and explain the match.
    """
    llm = AzureChatOpenAI(
        azure_endpoint=Config.AZURE_OPENAI_ENDPOINT,
        api_key=Config.AZURE_OPENAI_API_KEY,
        api_version=Config.AZURE_OPENAI_API_VERSION,
        deployment_name=Config.AZURE_OPENAI_DEPLOYMENT,
        temperature=0.3,
    )
    
    # Extract key characteristics
    prospect_info = {
        "name": prospect.get("name", "Unknown"),
        "country": prospect.get("country", "Unknown"),
        "store_count": prospect.get("store_count", 0),
        "price_eur": prospect.get("avg_suit_price_eur", 0),
        "wool": prospect.get("wool_percentage", "unknown"),
        "mtm": prospect.get("made_to_measure", "unknown"),
        "style": prospect.get("brand_style", "unknown"),
        "business": prospect.get("business_model", "unknown"),
    }
    
    client_info = similar_client.get("metadata", {})
    client_profile = similar_client.get("profile", "")
    
    prompt = f"""You are analyzing why a prospect brand is similar to an existing Confeções Lança client.

PROSPECT:
- Name: {prospect_info['name']}
- Country: {prospect_info['country']}
- Stores: {prospect_info['store_count']}
- Price: €{prospect_info['price_eur']}
- Wool: {prospect_info['wool']}
- Made-to-Measure: {prospect_info['mtm']}
- Style: {prospect_info['style']}
- Business Model: {prospect_info['business']}

LANÇA CLIENT (Most Similar - {similarity_score:.1f}% match):
- Name: {client_info.get('name', 'Unknown')}
- Country: {client_info.get('country', 'Unknown')}
- Stores: {client_info.get('store_count', 0)}
- Wool: {client_info.get('wool_percentage', 'unknown')}
- Made-to-Measure: {client_info.get('made_to_measure', 'unknown')}
- Style: {client_info.get('brand_style', 'unknown')}
- Business Model: {client_info.get('business_model', 'unknown')}
- Profile: {client_profile}

TASK:
Write a brief explanation (2-3 sentences) explaining why these brands are similar.
Focus on:
- Business size and structure (store count)
- Quality positioning (wool percentage, bespoke services)
- Brand positioning and style
- Business model alignment

Be concise and specific. Write in English.

Example format:
"This prospect is similar to [Client Name] because both are small boutique retailers (X stores) focusing on premium/luxury menswear with 100% wool suits and bespoke services. They share a similar brand positioning and target the same market segment."

Explanation:"""

    try:
        response = await llm.ainvoke(prompt)
        explanation = response.content if hasattr(response, 'content') else str(response)
        return explanation.strip()
    except Exception as e:
        print(f"[VECTOR-DB] Error generating similarity explanation: {e}")
        # Fallback explanation based on key similarities
        similarities = []
        
        prospect_stores = prospect_info.get("store_count", 0)
        client_stores = client_info.get("store_count", 0)
        if abs(prospect_stores - client_stores) <= 5:
            similarities.append(f"similar boutique size ({prospect_stores} vs {client_stores} stores)")
        
        if prospect_info.get("wool") == client_info.get("wool_percentage"):
            similarities.append("100% wool suits")
        
        if str(prospect_info.get("mtm")).lower() == str(client_info.get("made_to_measure", "")).lower():
            similarities.append("made-to-measure services")
        
        if prospect_info.get("style") == client_info.get("brand_style"):
            similarities.append(f"{prospect_info.get('style')} positioning")
        
        if similarities:
            return f"Similar to {client_info.get('name', 'client')} because both have: {', '.join(similarities)}."
        else:
            return f"Similar to {client_info.get('name', 'client')} ({similarity_score:.1f}% match) based on overall brand profile and positioning."


# ============================================================================
# SCORING FUNCTIONS - DATA-DRIVEN (Based on 18 Real Lança Clients)
# ============================================================================
#
# Thresholds derived from analysis of 18 existing Lança clients:
# - Price: Min €375, Max €1500, Median €800
# - Stores: Min 1, Max 30, Median 4
# - 100% Wool: 18/18 (100%)
# - Made-to-Measure: 14/18 (78%)
# - Own Brand: 15/18 (83%)
#

# Hard filter thresholds (based on min/max of existing clients)
HARD_FILTER_MIN_PRICE_EUR = 375   # Minimum price among 18 clients
HARD_FILTER_MAX_STORES = 30       # Maximum stores among 18 clients

# Scoring thresholds (based on median of existing clients)
IDEAL_PRICE_EUR = 800   # Median price of 18 clients
IDEAL_MAX_STORES = 4    # Median store count of 18 clients


def passes_hard_filters(prospect: Dict) -> Tuple[bool, str]:
    """
    Check if prospect passes hard filters based on 18 client analysis.
    
    Returns:
        Tuple of (passes: bool, rejection_reason: str or None)
    """
    price = prospect.get("avg_suit_price_eur", 0)
    stores = prospect.get("store_count", 0)
    
    # Parse store count if string
    if isinstance(stores, str):
        try:
            stores = int(stores) if stores.isdigit() else 0
        except:
            stores = 0
    
    # Filter 1: Price too low (if price is known)
    if isinstance(price, (int, float)) and price > 0 and price < HARD_FILTER_MIN_PRICE_EUR:
        return False, "price_too_low"
    
    # Filter 2: Too many stores
    if stores > HARD_FILTER_MAX_STORES:
        return False, "too_many_stores"
    
    return True, None


def calculate_price_score(price: float) -> int:
    """
    Calculate price score based on 18 client analysis.
    
    Thresholds:
    - €800+ (median of clients) = 30 pts (max)
    - €500-799 = 20 pts
    - €375-499 = 10 pts
    - Unknown (0) = 15 pts (don't penalize missing data)
    - Below €375 = 0 pts (should be filtered out)
    """
    if price == 0 or price is None:
        return 15  # Unknown price - neutral score
    elif price >= IDEAL_PRICE_EUR:
        return 30  # At or above median (ideal)
    elif price >= 500:
        return 20  # Good price point
    elif price >= HARD_FILTER_MIN_PRICE_EUR:
        return 10  # Acceptable minimum
    else:
        return 0  # Below threshold


def calculate_size_score(store_count: int) -> int:
    """
    Calculate store size score based on 18 client analysis.
    
    Thresholds:
    - 1-4 stores (median of clients) = 30 pts (max)
    - 5-10 stores = 20 pts
    - 11-20 stores = 10 pts
    - 21-30 stores = 5 pts (still within max client range)
    - 0 stores (B2B/unknown) = 25 pts (often good)
    """
    if store_count == 0:
        return 25  # B2B/Manufacturing or unknown
    elif store_count <= IDEAL_MAX_STORES:
        return 30  # At or below median (ideal)
    elif store_count <= 10:
        return 20  # Good size
    elif store_count <= 20:
        return 10  # Acceptable
    elif store_count <= HARD_FILTER_MAX_STORES:
        return 5   # Within range but large
    else:
        return 0  # Too big


def calculate_wool_score(wool_percentage: str) -> int:
    """
    Calculate wool score based on 18 client analysis.
    
    100% of Lança clients use 100% wool, so this is critical.
    - 100% wool = 15 pts (max)
    - Wool blend/mentioned = 5 pts
    - Unknown/Other = 0 pts
    """
    wool_str = str(wool_percentage).lower()
    if "100" in wool_str:
        return 15  # 100% wool (like all 18 clients)
    elif "wool" in wool_str or "lã" in wool_str:
        return 5   # Wool mentioned but not 100%
    else:
        return 0   # Unknown or synthetic


def calculate_mtm_score(made_to_measure: any) -> int:
    """
    Calculate made-to-measure score based on 18 client analysis.
    
    78% of Lança clients offer MTM, so it's preferred but not required.
    - MTM = True = 15 pts (max)
    - MTM = False = 5 pts (still acceptable, 22% of clients don't have it)
    - Unknown = 8 pts (neutral)
    """
    if made_to_measure is True or str(made_to_measure).lower() == "true":
        return 15  # Has MTM (like 78% of clients)
    elif made_to_measure is False or str(made_to_measure).lower() == "false":
        return 5   # No MTM (like 22% of clients)
    else:
        return 8   # Unknown


def get_market_strength_score(country_code: str) -> float:
    """
    Get market strength score based on existing Lança clients in that country.
    Unchanged from before - uses MARKET_STRENGTH_STATIC.
    """
    strength = MARKET_STRENGTH_STATIC.get(country_code, 0)
    return min(strength * 0.2, 10)  # Max 10 pts (reduced weight)


# ============================================================================
# MAIN SCORING FUNCTION (for database.py integration)
# ============================================================================

async def calculate_prospect_score(prospect: Dict) -> Tuple[Dict, List[Dict]]:
    """
    Calculate the final score for a prospect using DATA-DRIVEN scoring.
    
    NEW SCORING SYSTEM (based on 18 real Lança client analysis):
    - Price Score: 0-30 pts (€800+ ideal)
    - Size Score: 0-30 pts (1-4 stores ideal)
    - Wool Score: 0-15 pts (100% wool required)
    - MTM Score: 0-15 pts (78% of clients have MTM)
    - Similarity Score: 0-10 pts (similar to 18 clients)
    - Market Score: 0-10 pts (existing presence in country)
    
    Total: 0-100 points (simple, explainable)
    
    Also checks hard filters:
    - Price < €375 → rejection
    - Stores > 30 → rejection
    
    Returns:
        Tuple of (scores_dict, similar_clients_list)
    """
    # Check hard filters first
    passes, rejection_reason = passes_hard_filters(prospect)
    
    # Generate profile text for the prospect
    prospect_description = generate_client_profile_text(prospect)
    
    # Find similar clients (generates temporary embedding, not stored)
    similar_clients = await find_similar_clients(prospect_description, n_results=5)
    
    # Parse store count
    store_count = prospect.get("store_count", 0)
    if isinstance(store_count, str):
        try:
            store_count = int(store_count) if store_count.isdigit() else 0
        except:
            store_count = 0
    
    # Parse price
    price = prospect.get("avg_suit_price_eur", 0)
    if isinstance(price, str):
        try:
            price = float(price) if price.replace('.', '').isdigit() else 0
        except:
            price = 0
    
    # Calculate individual scores
    price_score = calculate_price_score(price)
    size_score = calculate_size_score(store_count)
    wool_score = calculate_wool_score(prospect.get("wool_percentage", "unknown"))
    mtm_score = calculate_mtm_score(prospect.get("made_to_measure", None))
    
    # Similarity score (0-10 pts)
    if similar_clients:
        top_similarity = similar_clients[0]["similarity"]  # Best match
        similarity_score = min(top_similarity * 0.1, 10)  # 0-10 pts
    else:
        similarity_score = 5  # Neutral
    
    # Market score (0-10 pts)
    country_code = prospect.get("country_code", "XX")
    market_score = get_market_strength_score(country_code)
    
    # Calculate final score (simple addition, max 100)
    final_score = (
        price_score +       # 0-30 pts
        size_score +        # 0-30 pts
        wool_score +        # 0-15 pts
        mtm_score +         # 0-15 pts
        similarity_score +  # 0-10 pts
        market_score        # 0-10 pts (reduced)
    )
    
    # If fails hard filters, cap score at 40
    if not passes:
        final_score = min(final_score, 40)
    
    # Build explanation
    most_similar = similar_clients[0] if similar_clients else None
    
    # Generate similarity explanation
    similarity_explanation = None
    if most_similar:
        try:
            similarity_explanation = await generate_similarity_explanation(
                prospect,
                most_similar,
                most_similar["similarity"]
            )
        except Exception as e:
            print(f"[VECTOR-DB] Warning: Could not generate similarity explanation: {e}")
            similarity_explanation = f"Similar to {most_similar['name']} ({most_similar['similarity']:.1f}% match) based on brand profile and positioning."
    
    # Determine size category
    if store_count <= IDEAL_MAX_STORES:
        size_category = "ideal boutique"
    elif store_count <= 10:
        size_category = "small chain"
    elif store_count <= 20:
        size_category = "medium chain"
    else:
        size_category = "large chain"
    
    scores = {
        "final_score": round(final_score, 2),
        "passes_hard_filters": passes,
        "rejection_reason": rejection_reason,
        "breakdown": {
            "price_score": price_score,       # 0-30
            "size_score": size_score,         # 0-30
            "wool_score": wool_score,         # 0-15
            "mtm_score": mtm_score,           # 0-15
            "similarity_score": round(similarity_score, 2),  # 0-10
            "market_score": round(market_score, 2),          # 0-10
        },
        "thresholds": {
            "ideal_price_eur": IDEAL_PRICE_EUR,
            "ideal_max_stores": IDEAL_MAX_STORES,
            "hard_filter_min_price": HARD_FILTER_MIN_PRICE_EUR,
            "hard_filter_max_stores": HARD_FILTER_MAX_STORES,
        },
        "explanation": {
            "price": f"€{price:.0f}" if price > 0 else "Unknown",
            "size": f"{store_count} stores → {size_category}",
            "wool": prospect.get("wool_percentage", "Unknown"),
            "mtm": "Yes" if prospect.get("made_to_measure") else "No/Unknown",
            "most_similar_client": most_similar["name"] if most_similar else "N/A",
            "similarity_to_best_match": most_similar["similarity"] if most_similar else 0,
            "similarity_explanation": similarity_explanation,
        }
    }
    
    return scores, similar_clients


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_recommendation(score: float) -> str:
    """Get recommendation based on score"""
    if score >= 80:
        return "⭐ HIGHLY RECOMMENDED - Ideal boutique partner"
    elif score >= 65:
        return "✅ RECOMMENDED - Good potential partner"
    elif score >= 50:
        return "⚠️ CONSIDER - Review manually"
    else:
        return "❌ LOW PRIORITY - May be too large or not aligned"


async def match_prospect_to_clients(prospect: Dict) -> Dict:
    """
    Match a prospect against Lança's client database.
    Returns match score and similar clients.
    """
    scores, similar_clients = await calculate_prospect_score(prospect)
    
    return {
        "prospect": prospect.get("name", "Unknown"),
        "scores": scores,
        "similar_clients": similar_clients[:5],
        "recommendation": get_recommendation(scores["final_score"]),
    }


def get_ideal_client_profiles() -> List[Dict]:
    """
    Get the profiles of IDEAL clients (small boutiques with high quality).
    """
    ideal_clients = []
    
    for client in LANCA_CLIENTS:
        stores = client.get("store_count", 0)
        wool = client.get("wool_percentage", "unknown")
        mtm = client.get("made_to_measure", False)
        
        is_small = (stores >= 1 and stores <= 10) or stores == 0
        is_quality = wool == "100%" or mtm == True
        
        if is_small and is_quality:
            ideal_clients.append(client)
    
    return ideal_clients


async def get_clients_count() -> int:
    """Get the number of Lança clients in the database."""
    pool = await PostgresManager.get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM lanca_clients")


# ============================================================================
# CLI FOR TESTING
# ============================================================================

if __name__ == "__main__":
    import asyncio
    
    async def test():
        print("=" * 60)
        print("Testing Vector DB Service (Simplified)")
        print("=" * 60)
        
        # 1. Populate clients database
        print("\n1. Populating clients database...")
        result = await populate_clients_database()
        print(f"   Result: {result['status']} ({result['count']} clients)")
        
        # 2. Test prospect scoring
        print("\n2. Testing prospect scoring...")
        test_prospect = {
            "name": "Test Boutique Milano",
            "website_url": "https://testboutique.it",
            "city": "Milan",
            "country": "Italy",
            "country_code": "IT",
            "store_count": 3,
            "avg_suit_price_eur": 750,
            "wool_percentage": "100%",
            "made_to_measure": True,
            "brand_style": "Premium/Boutique",
            "business_model": "Retail",
            "description": "Italian boutique tailor specializing in bespoke suits",
        }
        
        scores, similar = await calculate_prospect_score(test_prospect)
        print(f"   Prospect: {test_prospect['name']}")
        print(f"   Final Score: {scores['final_score']}")
        print(f"   Size Score: {scores['breakdown']['size_score']}")
        print(f"   Quality Score: {scores['breakdown']['quality_score']}")
        print(f"   Similarity Score: {scores['breakdown']['similarity_score']}")
        print(f"   Most Similar: {similar[0]['name'] if similar else 'N/A'}")
        print(f"   Recommendation: {get_recommendation(scores['final_score'])}")
        
        # 3. Check collection count
        print("\n3. Checking collection...")
        count = await get_clients_count()
        print(f"   Lança clients in PostgreSQL: {count}")
        
        print("\n" + "=" * 60)
        print("✅ All tests completed!")
        print("=" * 60)
    
    asyncio.run(test())
