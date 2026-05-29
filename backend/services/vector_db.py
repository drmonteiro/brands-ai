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

EMBEDDING_DIMENSIONS = 1536


def get_azure_embeddings() -> AzureOpenAIEmbeddings:
    """Azure embeddings pinned to text-embedding-3-small / 1536 (matches pgvector column)."""
    return AzureOpenAIEmbeddings(
        azure_endpoint=Config.AZURE_OPENAI_ENDPOINT,
        api_key=Config.AZURE_OPENAI_API_KEY,
        api_version=Config.AZURE_OPENAI_API_VERSION,
        azure_deployment=Config.AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
        dimensions=EMBEDDING_DIMENSIONS,
    )


# ============================================================================
# CLIENT PROFILE GENERATION (for embeddings)
# ============================================================================

def generate_client_profile_text(client: Dict) -> str:
    """
    Generate a rich, embedding-optimized text description of a Lança client.
    
    Enriched profile (V3) — includes partnership context, fabric preferences,
    service model, and positioning for higher-quality vector similarity.
    """
    name = client.get("name", "Unknown")
    brand_name = client.get("brand_name", name)
    country = client.get("country", "Unknown")
    city = client.get("city", None)
    years = client.get("years_as_client", None)
    brand_type = client.get("brand_type", "unknown")
    
    # Location
    location_text = f"{city}, {country}" if city and city != country else country
    
    # Price
    pvp = client.get("pvp_suits_eur", None)
    if pvp and isinstance(pvp, (int, float)):
        if pvp >= 1000:
            price_text = f"luxury suits priced at €{pvp}, targeting high-end clientele"
        elif pvp >= 600:
            price_text = f"premium suits priced at €{pvp}, mid-to-high segment"
        else:
            price_text = f"accessible premium suits priced at €{pvp}"
    else:
        price_text = "price positioning not public"
    
    # Store size
    stores = client.get("store_count", 0)
    if stores <= 2:
        store_text = f"exclusive single-boutique operation with {stores} store(s)"
    elif stores <= 5:
        store_text = f"small boutique retailer with {stores} stores"
    elif stores <= 10:
        store_text = f"established small chain with {stores} stores"
    elif stores <= 20:
        store_text = f"medium-sized retailer with {stores} stores"
    else:
        store_text = f"larger chain with {stores} stores"
    
    # Business model
    brand_style = client.get("brand_style", "Premium")
    business_model = client.get("business_model", "Retail")
    
    # Wool and MTM
    wool = client.get("wool_percentage", "unknown")
    mtm = client.get("made_to_measure", False)
    wool_text = "uses 100% pure wool for all suits" if wool == "100%" else f"wool usage: {wool}"
    mtm_text = "offers bespoke and made-to-measure tailoring services" if mtm else "focuses on ready-to-wear collections"
    
    # Brand type
    if brand_type == "own_brand":
        brand_type_text = "operates under their own brand name"
    elif brand_type == "multibrand":
        brand_type_text = f"multi-brand retailer distributing {brand_name}"
    else:
        brand_type_text = "independent retailer"
    
    # Partnership
    years_text = f"Long-term {years}-year manufacturing partnership with Confeções Lança." if years else ""
    tier = client.get("tier", "medium_value")
    tier_text = {"high_value": "High-value client.", "medium_value": "Established partner.", "low_value": "Growing relationship."}.get(tier, "")
    
    # Description
    description = client.get("description", "")
    notes = client.get("notes", "")
    
    parts = [
        f"{name} is a {brand_style.lower()} menswear brand based in {location_text}.",
        f"They are a {store_text}.",
        f"Price positioning: {price_text}.",
        f"Materials: {wool_text}.",
        f"Services: {mtm_text}.",
        f"Business model: {business_model}. {brand_type_text.capitalize()}.",
        years_text,
        tier_text,
        f"Profile: {description}" if description else "",
        f"Key characteristics: independent boutique, European manufacturing, quality Portuguese suits, premium menswear retail.",
    ]
    
    return " ".join(p for p in parts if p)


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
        "mtm": (
            "unknown"
            if prospect.get("made_to_measure") is None
            else prospect.get("made_to_measure")
        ),
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
# SCORING — delegated to services.scoring (extracted for modularity)
# Re-export for backward compatibility with existing imports.
# ============================================================================
from services.scoring import (  # noqa: F401
    calculate_prospect_score,
    passes_hard_filters,
    calculate_price_score,
    calculate_size_score,
    calculate_wool_score,
    calculate_mtm_score,
    get_market_strength_score,
    HARD_FILTER_MIN_PRICE_EUR,
    HARD_FILTER_MAX_STORES,
    IDEAL_PRICE_EUR,
    IDEAL_MAX_STORES,
)


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
