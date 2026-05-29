"""
PostgreSQL Vector Database Service for Confeções Lança

This service ONLY handles:
1. Storing embeddings of 18 TOP Lança clients (PERMANENT) using pgvector
2. Calculating similarity scores for prospects (TEMPORARY embeddings)
3. Prioritizing SMALL boutiques over large chains (Lança strategy)

IMPORTANT: Prospects are NOT stored here (see database.py)
"""

import asyncio
import os
import json
import logging
from typing import List, Dict, Optional, Tuple
from langchain_openai import AzureOpenAIEmbeddings

from config import Config
from data.lanca_clients import (
    LANCA_CLIENTS,
    MARKET_STRENGTH_STATIC,
    IDEAL_CLIENT_PROFILE,
    get_top_clients,
)
from .postgres import PostgresManager

logger = logging.getLogger("services.vector_db")

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


def _rows_to_similar_clients(rows) -> List[Dict]:
    similar_clients = []
    for row in rows:
        client_dict = dict(row)
        similarity = client_dict.pop("similarity_score")
        similar_clients.append({
            "id": client_dict["id"],
            "name": client_dict["name"],
            "country": client_dict["country"],
            "similarity": round(similarity * 100, 2),
            "metadata": client_dict,
            "profile": client_dict["profile_text"],
        })
    return similar_clients


async def _fetch_similar_for_embedding(
    conn,
    embedding: List[float],
    n_results: int,
) -> List[Dict]:
    rows = await conn.fetch(
        """
            SELECT *, 1 - (embedding <=> $1::vector) as similarity_score
            FROM lanca_clients
            ORDER BY embedding <=> $1::vector
            LIMIT $2
        """,
        str(embedding),
        n_results,
    )
    return _rows_to_similar_clients(rows)


async def find_similar_clients_batch(
    prospect_descriptions: List[str],
    n_results: int = 10,
    filter_metadata: Optional[Dict] = None,
) -> List[List[Dict]]:
    """
    Batch embedding + pgvector search. One API call for all inputs; order preserved.
    """
    if not prospect_descriptions:
        return []

    if filter_metadata:
        logger.debug("filter_metadata ignored in find_similar_clients_batch")

    pool = await PostgresManager.get_pool()
    embeddings_fn = get_azure_embeddings()
    vectors = await embeddings_fn.aembed_documents(list(prospect_descriptions))

    if len(vectors) != len(prospect_descriptions):
        raise ValueError(
            f"Embedding batch size mismatch: got {len(vectors)} for "
            f"{len(prospect_descriptions)} inputs"
        )

    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM lanca_clients")
    if count == 0:
        await populate_clients_database()

    async def _query_one(embedding: List[float]) -> List[Dict]:
        async with pool.acquire() as conn:
            return await _fetch_similar_for_embedding(conn, embedding, n_results)

    return list(await asyncio.gather(*[_query_one(v) for v in vectors]))


async def find_similar_clients(
    prospect_description: str,
    n_results: int = 10,
    filter_metadata: Optional[Dict] = None,
) -> List[Dict]:
    """Find the most similar Lança clients using pgvector (single prospect)."""
    batch = await find_similar_clients_batch(
        [prospect_description], n_results=n_results, filter_metadata=filter_metadata
    )
    return batch[0] if batch else []


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
    Debug helper: embedding similarity to Lança clients (no rubric/runtime score).
    Production ranking uses persistence.score_and_save_node + runtime_scoring.
    """
    prospect_description = generate_client_profile_text(prospect)
    similar_clients = await find_similar_clients(prospect_description, n_results=5)
    top_sim = similar_clients[0]["similarity"] if similar_clients else 0.0

    return {
        "prospect": prospect.get("name", "Unknown"),
        "similar_clients": similar_clients[:5],
        "top_similarity_pct": top_sim,
        "recommendation": get_recommendation(top_sim),
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
        
        # 2. Test similarity match
        print("\n2. Testing similarity match...")
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

        match = await match_prospect_to_clients(test_prospect)
        print(f"   Prospect: {test_prospect['name']}")
        print(f"   Top similarity: {match['top_similarity_pct']:.1f}%")
        sim = match["similar_clients"]
        print(f"   Most Similar: {sim[0]['name'] if sim else 'N/A'}")
        print(f"   Recommendation: {match['recommendation']}")
        
        # 3. Check collection count
        print("\n3. Checking collection...")
        count = await get_clients_count()
        print(f"   Lança clients in PostgreSQL: {count}")
        
        print("\n" + "=" * 60)
        print("✅ All tests completed!")
        print("=" * 60)
    
    asyncio.run(test())
