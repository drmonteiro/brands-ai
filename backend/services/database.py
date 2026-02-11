"""
PostgreSQL Database Service for Confeções Lança - Prospect Management

This service handles:
- Storing discovered prospects (unified relational + vector data)
- Filtering prospects by city
- Status tracking
- CRUD operations

Architecture:
- PostgreSQL + pgvector → Unified storage for everything
"""

import os
import json
import asyncio
from datetime import datetime
from typing import List, Dict, Optional, Any
from .postgres import PostgresManager

# ============================================================================
# DATABASE UTILITIES
# ============================================================================

async def get_db_conn():
    """Get an async connection from the pool."""
    pool = await PostgresManager.get_pool()
    return pool.acquire()


async def init_database():
    """
    Initialize the PostgreSQL database with required tables.
    """
    schema_path = os.path.join(os.path.dirname(__file__), "..", "migrations", "001_initial_schema.sql")
    if not os.path.exists(schema_path):
        print(f"❌ Schema file not found at {schema_path}")
        return

    with open(schema_path, "r") as f:
        schema_sql = f.read()

    try:
        pool = await PostgresManager.get_pool()
        async with pool.acquire() as conn:
            await conn.execute(schema_sql)
        print("[DATABASE] ✅ PostgreSQL database initialized")
    except Exception as e:
        print(f"[DATABASE] ❌ Initialization failed: {e}")
        print("💡 Make sure Docker is running: 'docker-compose up -d'")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def normalize_url(url: str) -> str:
    """Normalize URL for duplicate detection."""
    if not url:
        return ""
    normalized = url.lower().strip()
    normalized = normalized.replace("https://", "").replace("http://", "")
    normalized = normalized.replace("www.", "")
    normalized = normalized.rstrip("/")
    return normalized.split("?")[0].split("#")[0]


def extract_domain(url: str) -> str:
    """
    Extract just the base domain from a URL for brand-level deduplication.
    E.g., 'hmcole.com/boston-ma-schedule' -> 'hmcole.com'
    E.g., 'altonlane.com/custom-made/suits' -> 'altonlane.com'
    """
    if not url:
        return ""
    # First normalize the URL
    normalized = normalize_url(url)
    # Then extract just the domain (everything before the first /)
    domain = normalized.split("/")[0]
    return domain


def normalize_city(city: str) -> str:
    """Normalize city name for consistent storage."""
    return city.lower().strip()


def generate_prospect_id(normalized_url: str, normalized_city: str) -> str:
    """Generate unique ID for a prospect."""
    import hashlib
    return hashlib.md5(f"{normalized_url}_{normalized_city}".encode()).hexdigest()[:16]


# ============================================================================
# PROSPECT CRUD OPERATIONS
# ============================================================================

async def check_prospect_exists(website_url: str, city: str) -> bool:
    """
    Check if a prospect already exists for this city.
    Returns True if duplicate, False if new.
    """
    normalized_url = normalize_url(website_url)
    normalized_city = normalize_city(city)
    
    pool = await PostgresManager.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM prospects WHERE domain = $1 AND city = $2",
            extract_domain(normalized_url), normalized_city
        )
        return row is not None


async def save_prospect(
    prospect: Dict, 
    city: str, 
    scores: Dict,
    similar_clients: List[Dict] = None
) -> Dict:
    """
    Save a prospect to PostgreSQL.
    """
    website_url = prospect.get("website_url", "")
    normalized_url = normalize_url(website_url)
    domain = extract_domain(website_url)
    normalized_city = normalize_city(city)
    
    # Check for duplicate
    if await check_prospect_exists(website_url, city):
        print(f"[DATABASE] Duplicate found: {prospect.get('name')} in {city}")
        return {"status": "duplicate", "prospect": prospect}
    
    # Generate unique ID
    prospect_id = generate_prospect_id(normalized_url, normalized_city)
    
    pool = await PostgresManager.get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO prospects (
                id, name, website_url, domain, city, country, country_code,
                store_count, avg_suit_price_eur, brand_style, business_model, company_overview,
                detailed_description, store_locations,
                material_composition, sustainability_certs, made_to_measure,
                heritage_brand, quality_score, similarity_score, location_score, location_quality,
                final_score, fit_score, most_similar_client, similarity_explanation, status, discovered_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27, $28)
        """,
            prospect_id,
            str(prospect.get("name", "Unknown")),
            str(website_url),
            domain,
            normalized_city,
            str(prospect.get("country", "Unknown")),
            str(prospect.get("country_code", "XX")),
            int(prospect.get("store_count", 0)),
            float(prospect.get("avg_suit_price_eur", 0)),
            str(prospect.get("brand_style", "unknown")),
            str(prospect.get("business_model", "unknown")),
            str(prospect.get("description", "")),
            str(prospect.get("detailed_description", "")),
            json.dumps(prospect.get("store_locations", [])),
            json.dumps(prospect.get("material_composition", [])),
            json.dumps(prospect.get("sustainability_certs", [])),
            bool(prospect.get("made_to_measure", False)),
            bool(prospect.get("heritage_brand", False)),
            int(scores.get("breakdown", {}).get("quality_score", 0)),
            int(scores.get("breakdown", {}).get("similarity_score", 0)),
            int(scores.get("breakdown", {}).get("location_score", 0)),
            str(prospect.get("location_quality", "standard")),
            int(scores.get("final_score", 0)),
            int(prospect.get("fit_score", 0)),
            scores.get("explanation", {}).get("most_similar_client", "N/A"),
            scores.get("explanation", {}).get("similarity_explanation", ""),
            "new",
            datetime.now()
        )
        
        print(f"[DATABASE] ✅ Saved to Postgres: {prospect.get('name')} ({city}) - Score: {scores.get('final_score', 0):.1f}")
    
    return {"status": "saved", "id": prospect_id, "prospect": prospect}


async def get_prospects_by_city(city: str, limit: int = 25) -> List[Dict]:
    """
    Get all prospects for a specific city, ordered by score.
    """
    normalized_city = normalize_city(city)
    
    pool = await PostgresManager.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT DISTINCT ON (domain) * FROM prospects 
            WHERE city = $1
            ORDER BY domain, final_score DESC
            LIMIT $2
        """, normalized_city, limit)
        
        return [dict(row) for row in rows]


async def city_has_results(city: str) -> bool:
    """
    Check if a city has already been searched and has results in the database.
    """
    normalized_city = normalize_city(city)
    
    pool = await PostgresManager.get_pool()
    async with pool.acquire() as conn:
        count = await conn.fetchval("""
            SELECT COUNT(*) FROM prospects 
            WHERE city = $1
        """, normalized_city)
        return count > 0


async def get_all_prospects(limit: int = 100) -> List[Dict]:
    """
    Get all prospects across all cities, ordered by score.
    """
    pool = await PostgresManager.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT DISTINCT ON (domain) * FROM prospects 
            ORDER BY domain, final_score DESC
            LIMIT $1
        """, limit)
        return [dict(row) for row in rows]


# ============================================================================
# ADVANCED FILTERING SYSTEM
# ============================================================================

async def get_prospects_filtered(
    # Location filters
    city: Optional[str] = None,
    country: Optional[str] = None,
    country_code: Optional[str] = None,
    
    # Store count filters
    min_stores: Optional[int] = None,
    max_stores: Optional[int] = None,
    
    # Price filters (EUR)
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    
    # Score filters
    min_score: Optional[float] = None,
    max_score: Optional[float] = None,
    min_quality_score: Optional[float] = None,
    min_similarity_score: Optional[float] = None,
    
    # Categorical filters
    status: Optional[str] = None,
    statuses: Optional[List[str]] = None,
    brand_style: Optional[str] = None,
    brand_styles: Optional[List[str]] = None,
    business_model: Optional[str] = None,
    made_to_measure: Optional[str] = None,
    
    # Text search
    search_name: Optional[str] = None,
    similar_to_client: Optional[str] = None,
    
    # Sorting
    sort_by: str = "final_score",
    sort_order: str = "desc",
    
    # Pagination
    limit: int = 25,
    offset: int = 0,
) -> Dict:
    """
    Advanced filtering for prospects with multiple criteria.
    """
    conditions = []
    params = []
    
    if city:
        params.append(normalize_city(city))
        conditions.append(f"city = ${len(params)}")
    
    if country:
        params.append(f"%{country.lower()}%")
        conditions.append(f"LOWER(country) LIKE ${len(params)}")
    
    if country_code:
        params.append(country_code.upper())
        conditions.append(f"country_code = ${len(params)}")
    
    if min_stores is not None:
        params.append(min_stores)
        conditions.append(f"store_count >= ${len(params)}")
    
    if max_stores is not None:
        params.append(max_stores)
        conditions.append(f"store_count <= ${len(params)}")
    
    if min_price is not None:
        params.append(min_price)
        conditions.append(f"avg_suit_price_eur >= ${len(params)}")
    
    if max_price is not None:
        params.append(max_price)
        conditions.append(f"avg_suit_price_eur <= ${len(params)}")
    
    if min_score is not None:
        params.append(min_score)
        conditions.append(f"final_score >= ${len(params)}")
        
    if max_score is not None:
        params.append(max_score)
        conditions.append(f"final_score <= ${len(params)}")
        
    if min_quality_score is not None:
        params.append(min_quality_score)
        conditions.append(f"quality_score >= ${len(params)}")
        
    if min_similarity_score is not None:
        params.append(min_similarity_score)
        conditions.append(f"similarity_score >= ${len(params)}")
    
    if status:
        params.append(status)
        conditions.append(f"status = ${len(params)}")
    elif statuses:
        placeholders = []
        for s in statuses:
            params.append(s)
            placeholders.append(f"${len(params)}")
        conditions.append(f"status IN ({','.join(placeholders)})")
        
    if brand_style:
        params.append(brand_style)
        conditions.append(f"brand_style = ${len(params)}")
    elif brand_styles:
        placeholders = []
        for s in brand_styles:
            params.append(s)
            placeholders.append(f"${len(params)}")
        conditions.append(f"brand_style IN ({','.join(placeholders)})")
        
    if made_to_measure:
        if made_to_measure.lower() == "true":
            conditions.append("made_to_measure = TRUE")
        elif made_to_measure.lower() == "false":
            conditions.append("made_to_measure = FALSE")
            
    if search_name:
        params.append(f"%{search_name.lower()}%")
        conditions.append(f"LOWER(name) LIKE ${len(params)}")
        
    if business_model:
        params.append(business_model)
        conditions.append(f"business_model = ${len(params)}")
        
    if similar_to_client:
        params.append(f"%{similar_to_client.lower()}%")
        conditions.append(f"LOWER(most_similar_client) LIKE ${len(params)}")
    
    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
    
    valid_sort_columns = [
        "final_score", "store_count", "avg_suit_price_eur", 
        "discovered_at", "name", "quality_score", "similarity_score"
    ]
    if sort_by not in valid_sort_columns:
        sort_by = "final_score"
    
    sort_direction = "DESC" if sort_order.lower() == "desc" else "ASC"
    
    pool = await PostgresManager.get_pool()
    async with pool.acquire() as conn:
        # Deduplication using DISTINCT ON (domain)
        # Note: ORDER BY must start with the DISTINCT ON expression
        query = f"""
            SELECT * FROM (
                SELECT DISTINCT ON (domain) * FROM prospects
                {where_clause}
                ORDER BY domain, {sort_by} {sort_direction}
            ) sub
            ORDER BY {sort_by} {sort_direction}
            LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}
        """
        rows = await conn.fetch(query, *params, limit, offset)
        prospects = [dict(row) for row in rows]
        
        count_query = f"SELECT COUNT(DISTINCT domain) FROM prospects {where_clause}"
        total_count = await conn.fetchval(count_query, *params)
    
    return {
        "prospects": prospects,
        "total_count": total_count or 0,
        "returned_count": len(prospects),
        "limit": limit,
        "offset": offset,
        "has_more": (offset + len(prospects)) < (total_count or 0),
        "sort_by": sort_by,
        "sort_order": sort_order,
    }


# ============================================================================
# AGGREGATION & ANALYTICS
# ============================================================================

async def get_filter_options() -> Dict:
    """
    Get available options for filters (for UI dropdowns).
    """
    pool = await PostgresManager.get_pool()
    async with pool.acquire() as conn:
        statuses = [row['status'] for row in await conn.fetch("SELECT DISTINCT status FROM prospects WHERE status IS NOT NULL")]
        brand_styles = [row['brand_style'] for row in await conn.fetch("SELECT DISTINCT brand_style FROM prospects WHERE brand_style != 'unknown'")]
        countries = [row['country'] for row in await conn.fetch("SELECT DISTINCT country FROM prospects WHERE country != 'Unknown' ORDER BY country")]
        cities = [row['city'] for row in await conn.fetch("SELECT DISTINCT city FROM prospects ORDER BY city")]
        
        ranges = await conn.fetchrow("""
            SELECT 
                MIN(avg_suit_price_eur) as min_price, MAX(avg_suit_price_eur) as max_price,
                MIN(store_count) as min_stores, MAX(store_count) as max_stores,
                MIN(final_score) as min_score, MAX(final_score) as max_score
            FROM prospects
        """)
    
    return {
        "statuses": statuses,
        "brand_styles": brand_styles,
        "countries": countries,
        "cities": cities,
        "made_to_measure_options": ["true", "false", "unknown"],
        "ranges": {
            "price": {"min": ranges['min_price'] or 0, "max": ranges['max_price'] or 5000},
            "stores": {"min": ranges['min_stores'] or 0, "max": ranges['max_stores'] or 100},
            "score": {"min": ranges['min_score'] or 0, "max": ranges['max_score'] or 100},
        },
    }


async def get_price_analysis() -> Dict:
    """
    Get detailed price analysis for the dashboard.
    """
    pool = await PostgresManager.get_pool()
    async with pool.acquire() as conn:
        # Price distribution
        prices = await conn.fetch("""
            SELECT 
                CASE 
                    WHEN avg_suit_price_eur < 500 THEN '< 500€'
                    WHEN avg_suit_price_eur >= 500 AND avg_suit_price_eur < 1000 THEN '500€ - 1000€'
                    WHEN avg_suit_price_eur >= 1000 AND avg_suit_price_eur < 2000 THEN '1000€ - 2000€'
                    ELSE '> 2000€'
                END as bracket,
                COUNT(*) as count,
                AVG(final_score) as avg_score
            FROM prospects
            WHERE avg_suit_price_eur > 0
            GROUP BY bracket
            ORDER BY MIN(avg_suit_price_eur)
        """)
        
        # General stats
        stats = await conn.fetchrow("""
            SELECT 
                MIN(avg_suit_price_eur) as min_price,
                MAX(avg_suit_price_eur) as max_price,
                AVG(avg_suit_price_eur) as avg_price
            FROM prospects
            WHERE avg_suit_price_eur > 0
        """)
        
    return {
        "distribution": [dict(p) for p in prices],
        "stats": dict(stats) if stats else {},
    }


async def get_store_count_analysis() -> Dict:
    """
    Get detailed store count analysis.
    """
    pool = await PostgresManager.get_pool()
    async with pool.acquire() as conn:
        counts = await conn.fetch("""
            SELECT 
                CASE 
                    WHEN store_count <= 5 THEN 'Boutique (1-5)'
                    WHEN store_count > 5 AND store_count <= 20 THEN 'Medium (6-20)'
                    ELSE 'Retailer (20+)'
                END as bracket,
                COUNT(*) as count,
                AVG(final_score) as avg_score
            FROM prospects
            WHERE store_count > 0
            GROUP BY bracket
            ORDER BY MIN(store_count)
        """)
        
    return {
        "distribution": [dict(c) for c in counts]
    }


async def get_dashboard_stats() -> Dict:
    """
    Get comprehensive dashboard statistics.
    """
    pool = await PostgresManager.get_pool()
    async with pool.acquire() as conn:
        total_prospects = await conn.fetchval("SELECT COUNT(*) FROM prospects")
        if total_prospects == 0:
            return {"total_prospects": 0}
            
        status_counts = await conn.fetch("SELECT status, COUNT(*) as count FROM prospects GROUP BY status")
        city_counts = await conn.fetch("SELECT city, COUNT(*) as count FROM prospects GROUP BY city ORDER BY count DESC LIMIT 10")
        
        score_stats = await conn.fetchrow("""
            SELECT 
                SUM(CASE WHEN final_score >= 80 THEN 1 ELSE 0 END) as excellent,
                SUM(CASE WHEN final_score >= 65 AND final_score < 80 THEN 1 ELSE 0 END) as good,
                SUM(CASE WHEN final_score >= 50 AND final_score < 65 THEN 1 ELSE 0 END) as average,
                SUM(CASE WHEN final_score < 50 THEN 1 ELSE 0 END) as low
            FROM prospects
        """)
    
    return {
        "total_prospects": total_prospects,
        "by_status": {row['status']: row['count'] for row in status_counts},
        "by_city": [dict(row) for row in city_counts],
        "score_distribution": dict(score_stats) if score_stats else {},
    }


async def get_city_stats(city: str) -> Dict:
    """
    Get statistics for a specific city.
    """
    normalized_city = normalize_city(city)
    pool = await PostgresManager.get_pool()
    async with pool.acquire() as conn:
        stats = await conn.fetchrow("""
            SELECT 
                COUNT(*) as total_prospects,
                AVG(final_score) as avg_score,
                MAX(final_score) as top_score
            FROM prospects
            WHERE city = $1
        """, normalized_city)
    
    if not stats or stats['total_prospects'] == 0:
        return {"total_prospects": 0}
        
    return {
        "city": city,
        "total_prospects": stats['total_prospects'],
        "avg_score": round(stats['avg_score'] or 0, 2),
        "top_score": round(stats['top_score'] or 0, 2),
    }


async def get_all_searched_cities() -> List[Dict]:
    """
    Get all cities that have been searched with their stats.
    """
    pool = await PostgresManager.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT 
                city,
                COUNT(*) as total_prospects,
                AVG(final_score) as avg_score,
                MAX(final_score) as top_score,
                SUM(CASE WHEN status = 'new' THEN 1 ELSE 0 END) as new_count,
                SUM(CASE WHEN status = 'contacted' THEN 1 ELSE 0 END) as contacted_count,
                SUM(CASE WHEN status = 'converted' THEN 1 ELSE 0 END) as converted_count
            FROM prospects
            GROUP BY city
            ORDER BY total_prospects DESC
        """)
        return [dict(row) for row in rows]


async def get_existing_urls_for_city(city: str) -> set:
    """
    Get existing normalized URLs for a city.
    """
    normalized_city = normalize_city(city)
    pool = await PostgresManager.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT domain FROM prospects WHERE city = $1", normalized_city)
        return {row['domain'] for row in rows}


async def update_prospect_status(prospect_id: str, status: str, notes: Optional[str] = None):
    """
    Update prospect status and notes.
    """
    pool = await PostgresManager.get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE prospects 
            SET status = $1, notes = $2, updated_at = CURRENT_TIMESTAMP 
            WHERE id = $3
        """, status, notes, prospect_id)


async def get_prospect_by_id(prospect_id: str) -> Optional[Dict]:
    """
    Get a single prospect by ID.
    """
    pool = await PostgresManager.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM prospects WHERE id = $1", prospect_id)
        return dict(row) if row else None


async def delete_prospect(prospect_id: str):
    """
    Delete a prospect by ID.
    """
    pool = await PostgresManager.get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM prospects WHERE id = $1", prospect_id)


# ============================================================================
# RGPD/GDPR SUPPRESSION LIST
# ============================================================================

async def is_domain_suppressed(domain: str) -> bool:
    """Check if a domain is in the suppression list."""
    pool = await PostgresManager.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM suppression_list WHERE domain = $1",
            domain.lower().strip()
        )
        return row is not None

async def add_to_suppression_list(domain: str, reason: str = "Unsubscribed"):
    """Add a domain to the suppression list."""
    pool = await PostgresManager.get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO suppression_list (domain, reason) VALUES ($1, $2) ON CONFLICT (domain) DO NOTHING",
            domain.lower().strip(), reason
        )


async def process_and_save_prospects(
    prospects: List[Dict],
    city: str,
    calculate_scores_fn,
) -> Dict:
    """
    Process and save a list of prospects.
    """
    print(f"\n[DATABASE] Processing {len(prospects)} prospects for {city}...")
    
    existing_domains = await get_existing_urls_for_city(city)
    new_count = 0
    duplicate_count = 0
    
    for prospect in prospects:
        domain = extract_domain(prospect.get("website_url", ""))
        
        if domain in existing_domains:
            duplicate_count += 1
            continue
        
        scores, similar_clients = await calculate_scores_fn(prospect)
        result = await save_prospect(prospect, city, scores, similar_clients)
        
        if result["status"] == "saved":
            new_count += 1
            existing_domains.add(domain)
    
    all_prospects = await get_prospects_by_city(city, limit=25)
    stats = await get_city_stats(city)
    
    return {
        "city": city,
        "new_saved": new_count,
        "duplicates_skipped": duplicate_count,
        "total_for_city": len(all_prospects),
        "stats": stats,
        "prospects": all_prospects,
    }
